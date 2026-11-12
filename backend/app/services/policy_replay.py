"""Reproducible inventory policy replay under identical demand/lead paths.

Compares:
  (a) fixed rule (reorder-point / pack)
  (b) demand-only forecast + pack cover
  (c) full multi-agent optimizer decision
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

import numpy as np

from app.core.config import settings
from app.services.scenarios import ScenarioInput, simulate_stock_path


def _rule_qty(stock: int, reorder_point: int, pack: int, budget: int, unit_cost: int) -> int:
    if stock >= reorder_point:
        return 0
    need = max(0, reorder_point * 2 - stock)
    packs = (need + pack - 1) // max(1, pack)
    qty = packs * pack
    if unit_cost > 0:
        max_q = budget // unit_cost
        qty = min(qty, (max_q // pack) * pack)
    return int(qty)


def _demand_only_qty(
    stock: int, daily_demand: float, lead_days: int, pack: int, budget: int, unit_cost: int
) -> int:
    cover = daily_demand * (lead_days + 14)
    need = max(0.0, cover - stock)
    packs = int(np.ceil(need / max(1, pack)))
    qty = packs * pack
    if unit_cost > 0:
        max_q = budget // unit_cost
        qty = min(qty, (max_q // pack) * pack)
    return int(qty)


def replay_policies_for_product(
    *,
    stock: int,
    daily_demand: float,
    lead_days: int,
    pack: int,
    reorder_point: int,
    unit_cost: int,
    budget: int,
    multi_agent_qty: int,
    horizon: int = 28,
    holding_rate: float = 0.02,
    shortage_frac: float = 0.3,
) -> dict[str, Any]:
    """Evaluate three policies on the SAME deterministic demand path."""
    policies = {
        "fixed_rule": _rule_qty(stock, reorder_point, pack, budget, unit_cost),
        "demand_only": _demand_only_qty(stock, daily_demand, lead_days, pack, budget, unit_cost),
        "multi_agent": max(0, int(multi_agent_qty)),
    }
    rows = []
    for name, qty in policies.items():
        if unit_cost > 0:
            qty = min(qty, (budget // unit_cost // pack) * pack) if pack else qty
        path = simulate_stock_path(
            ScenarioInput(
                stock_on_hand=stock,
                daily_demand_p50=daily_demand,
                order_qty=qty,
                lead_days=lead_days,
                pack_size=pack,
                horizon_days=horizon,
            )
        )
        purchase = qty * unit_cost
        holding = path.ending_stock * unit_cost * holding_rate
        shortage = path.unmet_demand_units * unit_cost * shortage_frac
        fulfilled = max(0.0, horizon * daily_demand - path.unmet_demand_units)
        revenue = fulfilled * unit_cost * 1.4
        cogs = fulfilled * unit_cost
        carried = float(np.mean([d["stock"] for d in path.days])) if path.days else 0.0
        rows.append(
            {
                "strategy": name,
                "order_units": qty,
                "reorder_events": 1 if qty > 0 else 0,
                "stockout_days": path.stockout_days,
                "unmet_demand_units": path.unmet_demand_units,
                "fulfilled_demand_units": fulfilled,
                "ending_stock": path.ending_stock,
                "avg_inventory": carried,
                "inventory_carried": carried,
                "holding_cost_paise": holding,
                "shortage_penalty_paise": shortage,
                "purchasing_cash_paise": purchase,
                "cogs_paise": cogs,
                "revenue_paise": revenue,
                "total_defined_cost_paise": holding + shortage,
                "note": "SIMULATED identical demand path; purchasing cash is not a loss and is excluded from defined cost",
            }
        )
    return {"label": "SIMULATED_POLICY_REPLAY", "seed": "deterministic_path", "rows": rows}


def stratified_product_ids(conn: sqlite3.Connection, *, sample: int = 50, seed: int = 42) -> list[int]:
    """Reproducible sample across demand level, intermittence, category, supplier, and risk."""
    rows = conn.execute(
        """
        SELECT p.id AS id, p.category AS category, p.supplier_id AS supplier_id,
               COALESCE(r.risk_level, 'unknown') AS risk,
               COALESCE(AVG(s.units), 0) AS avg_units,
               COALESCE(AVG(CASE WHEN s.units = 0 THEN 1.0 ELSE 0.0 END), 1.0) AS zero_share,
               COUNT(s.id) AS sale_days
        FROM products p
        LEFT JOIN sales s ON s.product_id = p.id
        LEFT JOIN product_risk_cache r ON r.product_id = p.id
        WHERE p.is_active = 1
        GROUP BY p.id
        ORDER BY p.id
        """
    ).fetchall()
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: (float(row["avg_units"]), int(row["id"])))
    quartile = max(1, len(ordered) // 4)
    low = {int(row["id"]) for row in ordered[:quartile]}
    high = {int(row["id"]) for row in ordered[-quartile:]}
    intermittent = {int(row["id"]) for row in rows if float(row["zero_share"]) >= 0.35}
    if not intermittent:
        counts = sorted(int(row["sale_days"]) for row in rows)
        median_days = counts[len(counts) // 2]
        intermittent = {int(row["id"]) for row in rows if int(row["sale_days"]) <= median_days}
    groups: list[list[int]] = [
        sorted(high),
        sorted(low),
        sorted(intermittent),
    ]
    for key in ("category", "supplier_id", "risk"):
        buckets: dict[object, list[int]] = {}
        for row in rows:
            buckets.setdefault(row[key], []).append(int(row["id"]))
        for bucket in buckets.values():
            groups.append(sorted(bucket))
    rng = np.random.default_rng(int(seed))
    shuffled: list[list[int]] = []
    for group in groups:
        if not group:
            continue
        picks = [int(value) for value in rng.permutation(group)]
        shuffled.append(picks)
    picked: list[int] = []
    seen: set[int] = set()
    while len(picked) < int(sample) and any(shuffled):
        for group in shuffled:
            while group and group[-1] in seen:
                group.pop()
            if not group:
                continue
            product_id = group.pop()
            if product_id in seen:
                continue
            seen.add(product_id)
            picked.append(product_id)
            if len(picked) >= int(sample):
                break
    return picked


def evaluate_policy_replay(
    conn: sqlite3.Connection,
    *,
    sample: int = 5,
    stratified: bool = False,
    seed: int = 42,
) -> dict[str, Any]:
    from app.services.orchestrator import run_decision

    started = time.perf_counter()
    if stratified:
        chosen = stratified_product_ids(conn, sample=sample, seed=seed)
        if not chosen:
            ids = []
        else:
            marks = ",".join("?" * len(chosen))
            ids = conn.execute(
                f"""
                SELECT id, stock_on_hand, reorder_point, pack_size, unit_cost_paise
                FROM products
                WHERE id IN ({marks})
                """,
                chosen,
            ).fetchall()
            order = {product_id: index for index, product_id in enumerate(chosen)}
            ids = sorted(ids, key=lambda row: order[int(row["id"])])
    else:
        ids = conn.execute(
            "SELECT id, stock_on_hand, reorder_point, pack_size, unit_cost_paise FROM products ORDER BY id LIMIT ?",
            (sample,),
        ).fetchall()
    agg: dict[str, dict[str, float]] = {}
    n = 0
    for r in ids:
        pid = int(r["id"])
        try:
            dec = run_decision(conn, pid, persist_trace=False)
        except Exception:
            continue
        avg = conn.execute(
            "SELECT AVG(units) FROM sales WHERE product_id=?", (pid,)
        ).fetchone()[0]
        lead = conn.execute(
            """
            SELECT s.base_lead_days FROM suppliers s
            JOIN products p ON p.supplier_id=s.id WHERE p.id=?
            """,
            (pid,),
        ).fetchone()
        daily = float(dec.get("agents", {}).get("p50_units") or avg or 1.0)
        result = replay_policies_for_product(
            stock=int(r["stock_on_hand"]),
            daily_demand=daily,
            lead_days=int(lead["base_lead_days"]) if lead else 7,
            pack=int(r["pack_size"]),
            reorder_point=int(r["reorder_point"]),
            unit_cost=int(r["unit_cost_paise"]),
            budget=500_000,
            multi_agent_qty=int(dec.get("suggested_qty") or 0),
        )
        for row in result["rows"]:
            s = row["strategy"]
            bucket = agg.setdefault(
                s,
                {
                    "order_units": 0.0,
                    "reorder_events": 0.0,
                    "stockout_days": 0.0,
                    "unmet_demand_units": 0.0,
                    "fulfilled_demand_units": 0.0,
                    "inventory_carried": 0.0,
                    "holding_cost_paise": 0.0,
                    "shortage_penalty_paise": 0.0,
                    "purchasing_cash_paise": 0.0,
                    "total_defined_cost_paise": 0.0,
                },
            )
            for k in bucket:
                bucket[k] += float(row[k])
        n += 1

    rows_out = []
    for strategy, bucket in agg.items():
        note = "Measured SIMULATED replay on identical paths"
        if n:
            avg_cost = bucket["total_defined_cost_paise"] / n
        else:
            avg_cost = None
        rows_out.append(
            {
                "strategy": strategy,
                "sample_skus": n,
                "mean_stockout_days": bucket["stockout_days"] / max(1, n),
                "mean_unmet_demand_units": bucket["unmet_demand_units"] / max(1, n),
                "mean_order_units": bucket["order_units"] / max(1, n),
                "mean_reorder_events": bucket["reorder_events"] / max(1, n),
                "mean_fulfilled_demand_units": bucket["fulfilled_demand_units"] / max(1, n),
                "mean_inventory_carried": bucket["inventory_carried"] / max(1, n),
                "mean_holding_cost_paise": bucket["holding_cost_paise"] / max(1, n),
                "mean_shortage_penalty_paise": bucket["shortage_penalty_paise"] / max(1, n),
                "mean_purchasing_cash_paise": bucket["purchasing_cash_paise"] / max(1, n),
                "mean_total_defined_cost_paise": avg_cost,
                # Keep savings_paise key for UI compatibility but label as cost, not savings
                "savings_paise": None,
                "cost_paise": int(avg_cost) if avg_cost is not None else None,
                "note": note,
            }
        )
    elapsed = time.perf_counter() - started
    return {
        "label": "SIMULATED_POLICY_REPLAY",
        "sample_skus": n,
        "requested_sample": int(sample),
        "stratified": bool(stratified),
        "seed": int(seed),
        "runtime_seconds": round(elapsed, 3),
        "rows": rows_out,
        "limitation": (
            "SIMULATED comparison on identical constant-demand paths. "
            "Purchasing cash is reported separately and is not treated as a saving or a loss. "
            "A lower defined cost on this sample is not evidence of real-world superiority."
        ),
    }


def write_expanded_replay(conn: sqlite3.Connection, *, sample: int = 50, seed: int = 42) -> dict[str, Any]:
    """Run a larger stratified replay and keep the stored 5-SKU result as history."""
    settings.ensure_dirs()
    payload = evaluate_policy_replay(conn, sample=sample, stratified=True, seed=seed)
    historical = None
    eval_path = settings.eval_dir / "latest_eval.json"
    if eval_path.exists():
        try:
            historical = json.loads(eval_path.read_text(encoding="utf-8")).get("business")
        except json.JSONDecodeError:
            historical = None
    payload["historical_five_sku_benchmark"] = historical
    payload["historical_five_note"] = (
        "The five-SKU benchmark is the previously stored evaluate_all replay. "
        "It was not refit on the expanded scenarios."
    )
    out = settings.eval_dir / "policy_replay_expanded.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["path"] = str(out)
    return payload
