"""Reproducible inventory policy replay under identical demand/lead paths.

Compares:
  (a) fixed rule (reorder-point / pack)
  (b) demand-only forecast + pack cover
  (c) full multi-agent optimizer decision
"""

from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np

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
        revenue = max(0.0, horizon * daily_demand - path.unmet_demand_units) * unit_cost * 1.4
        cogs = max(0.0, horizon * daily_demand - path.unmet_demand_units) * unit_cost
        total_cost = holding + shortage + purchase * 0.0  # purchase is cash, not double-counted loss
        # Defined economic cost for comparison: holding + shortage (cash reported separately)
        rows.append(
            {
                "strategy": name,
                "order_units": qty,
                "stockout_days": path.stockout_days,
                "unmet_demand_units": path.unmet_demand_units,
                "ending_stock": path.ending_stock,
                "avg_inventory": float(np.mean([d["stock"] for d in path.days])) if path.days else 0.0,
                "holding_cost_paise": holding,
                "shortage_penalty_paise": shortage,
                "purchasing_cash_paise": purchase,
                "cogs_paise": cogs,
                "revenue_paise": revenue,
                "total_defined_cost_paise": holding + shortage,
                "note": "SIMULATED identical demand path; cash outlay reported separately from economic cost",
            }
        )
    return {"label": "SIMULATED_POLICY_REPLAY", "seed": "deterministic_path", "rows": rows}


def evaluate_policy_replay(conn: sqlite3.Connection, *, sample: int = 5) -> dict[str, Any]:
    from app.services.orchestrator import run_decision

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
                    "stockout_days": 0.0,
                    "unmet_demand_units": 0.0,
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
    return {"label": "SIMULATED_POLICY_REPLAY", "sample_skus": n, "rows": rows_out}
