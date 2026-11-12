"""What-if simulation API helper — forecast-based inventory paths."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from app.agents.registry import get_agent
from app.core.config import settings
from app.db import repositories as repo
from app.services.scenarios import ScenarioInput, simulate_stock_path


def _normalize_qty(reorder_qty: int, pack: int, budget_paise: int, unit_cost: int) -> tuple[int, int, str]:
    """Return (requested, applied, note). Pack multiples enforced after budget clip."""
    requested = max(0, int(reorder_qty))
    note_parts: list[str] = []
    applied = requested
    if unit_cost > 0 and budget_paise >= 0:
        max_by_budget = budget_paise // unit_cost
        if applied > max_by_budget:
            applied = max_by_budget
            note_parts.append(f"clipped to budget max {max_by_budget} units")
    if pack > 1 and applied % pack != 0:
        applied = (applied // pack) * pack
        note_parts.append(f"rounded down to pack multiple of {pack}")
    if applied == 0 and requested > 0:
        note_parts.append("infeasible under budget/pack constraints — applied 0")
    note = "; ".join(note_parts) if note_parts else "requested quantity feasible"
    return requested, applied, note


def run_simulate(
    conn: sqlite3.Connection,
    *,
    product_id: int,
    reorder_qty: int,
    proposed_price_paise: int,
    lead_time_days: int,
    budget_paise: int,
    horizon_days: int = 28,
) -> dict:
    product = repo.get_product(conn, product_id)
    if not product:
        raise ValueError("Product not found")

    cost = int(product["unit_cost_paise"])
    pack = int(product["pack_size"])
    requested_qty, reorder_qty, qty_note = _normalize_qty(
        reorder_qty, pack, budget_paise, cost
    )

    price_base = int(product["selling_price_paise"])
    price_delta = 0.0
    price_effect_type = "none"
    p50_base = 1.0
    p50 = 1.0

    # Baseline demand at current shelf price
    try:
        demand = get_agent("demand")
        demand.load()
        # Observational price-response delta (not causal elasticity)
        try:
            pr = get_agent("price_response")
            pr.load()
            pr_out = pr.predict(
                conn, product_id, proposed_price_paise=proposed_price_paise
            ).output
            price_delta = float(pr_out.get("expected_units_delta") or 0.0)
            price_effect_type = pr_out.get("effect_type", "observational_association")
        except FileNotFoundError:
            price_delta = 0.0
            price_effect_type = "price_response_unavailable"

        d_base = demand.predict(conn, product_id, proposed_price_paise=price_base)
        p50_base = float(d_base.output.get("p50_units", 1.0))

        d_prop = demand.predict(
            conn,
            product_id,
            proposed_price_paise=proposed_price_paise,
            price_units_delta=price_delta,
        )
        p50 = float(d_prop.output.get("p50_units", p50_base))
    except Exception:
        row = conn.execute(
            """
            SELECT AVG(units) FROM sales
            WHERE product_id=? AND sale_date >= date(?, '-28 days')
            """,
            (product_id, settings.demo_date),
        ).fetchone()
        p50_base = p50 = float(row[0] or 1.0)
        price_effect_type = "fallback_mean_no_price_effect"

    so_risk_b = so_risk_p = None
    ex_risk_p = None
    try:
        so = get_agent("stockout_risk")
        so.load()
        so_risk_b = float(
            so.predict(
                conn,
                product_id,
                eta_days=lead_time_days,
                lead_days=lead_time_days,
                order_qty=0,
                daily_demand=p50_base,
            ).output.get("stockout_risk", 0.3)
        )
        so_risk_p = float(
            so.predict(
                conn,
                product_id,
                eta_days=lead_time_days,
                lead_days=lead_time_days,
                order_qty=reorder_qty,
                daily_demand=p50,
            ).output.get("stockout_risk", 0.2)
        )
    except Exception:
        pass
    try:
        ex = get_agent("excess_risk")
        ex.load()
        ex_risk_p = float(
            ex.predict(
                conn,
                product_id,
                eta_days=lead_time_days,
                order_qty=reorder_qty,
                daily_demand=p50,
            ).output.get("excess_risk", 0.1)
        )
    except Exception:
        pass

    base_qty = 0
    recs = [
        r
        for r in repo.get_open_recommendations(conn, limit=20)
        if r["product_id"] == product_id
    ]
    if recs:
        base_qty = int(recs[0]["suggested_qty"])

    stock = int(product["stock_on_hand"])
    base_path = simulate_stock_path(
        ScenarioInput(
            stock_on_hand=stock,
            daily_demand_p50=p50_base,
            order_qty=base_qty,
            lead_days=int(product.get("base_lead_days") or lead_time_days),
            pack_size=pack,
            horizon_days=horizon_days,
        )
    )
    prop_path = simulate_stock_path(
        ScenarioInput(
            stock_on_hand=stock,
            daily_demand_p50=p50,
            order_qty=reorder_qty,
            lead_days=lead_time_days,
            pack_size=pack,
            horizon_days=horizon_days,
        )
    )

    as_of = datetime.fromisoformat(settings.demo_date).date()

    def series(path):
        out = []
        for d in path.days:
            day = as_of + timedelta(days=int(d["day"]))
            out.append({"date": day.isoformat(), "inventory": int(d["stock"])})
        return out

    # Revenue / COGS / cash — do NOT call purchase spend "gross margin"
    fulfilled_base = max(0.0, horizon_days * p50_base - base_path.unmet_demand_units)
    fulfilled_prop = max(0.0, horizon_days * p50 - prop_path.unmet_demand_units)
    rev_b = int(fulfilled_base * price_base)
    rev_p = int(fulfilled_prop * proposed_price_paise)
    cogs_b = int(fulfilled_base * cost)
    cogs_p = int(fulfilled_prop * cost)
    cash_b = int(base_qty * cost)
    cash_p = int(reorder_qty * cost)
    margin_b = rev_b - cogs_b
    margin_p = rev_p - cogs_p

    arrival = (as_of + timedelta(days=lead_time_days)).isoformat()

    def fmt_pct(x):
        return f"{100 * x:.1f}%" if x is not None else "N/A"

    comparison = [
        {
            "metric": "Projected revenue (fulfilled × price)",
            "baseline": rev_b,
            "proposed": rev_p,
            "delta": f"{rev_p - rev_b:+d} paise",
        },
        {
            "metric": "Forecast demand u/day",
            "baseline": round(p50_base, 3),
            "proposed": round(p50, 3),
            "delta": f"{p50 - p50_base:+.3f}",
        },
        {
            "metric": "Stockout days (path)",
            "baseline": base_path.stockout_days,
            "proposed": prop_path.stockout_days,
            "delta": f"{prop_path.stockout_days - base_path.stockout_days:+d}",
        },
        {
            "metric": "Unmet demand units",
            "baseline": round(base_path.unmet_demand_units, 2),
            "proposed": round(prop_path.unmet_demand_units, 2),
            "delta": f"{prop_path.unmet_demand_units - base_path.unmet_demand_units:+.2f}",
        },
        {
            "metric": "Simulated stockout risk",
            "baseline": fmt_pct(so_risk_b),
            "proposed": fmt_pct(so_risk_p),
            "delta": None,
        },
        {
            "metric": "Purchase cash outlay",
            "baseline": cash_b,
            "proposed": cash_p,
            "delta": f"{cash_p - cash_b:+d} paise",
        },
        {
            "metric": "Gross margin (rev − COGS)",
            "baseline": margin_b,
            "proposed": margin_p,
            "delta": f"{margin_p - margin_b:+d} paise",
        },
    ]

    return {
        "baseline_label": "Current plan",
        "proposed_label": "Proposed plan (What-If)",
        "baseline_series": series(base_path),
        "proposed_series": series(prop_path),
        "baseline_metrics": {
            "stockout_days": base_path.stockout_days,
            "unmet_demand_units": base_path.unmet_demand_units,
            "stockout_probability": so_risk_b,
            "excess_risk_units": None,
            "purchase_cost_paise": cash_b,
            "revenue_paise": rev_b,
            "gross_margin_paise": margin_b,
            "cogs_paise": cogs_b,
            "demand_p50": p50_base,
        },
        "proposed_metrics": {
            "stockout_days": prop_path.stockout_days,
            "unmet_demand_units": prop_path.unmet_demand_units,
            "stockout_probability": so_risk_p,
            "excess_risk_units": ex_risk_p,
            "purchase_cost_paise": cash_p,
            "revenue_paise": rev_p,
            "gross_margin_paise": margin_p,
            "cogs_paise": cogs_p,
            "demand_p50": p50,
        },
        "comparison_rows": comparison,
        "arrival_date": arrival,
        "requested_qty": requested_qty,
        "applied_qty": reorder_qty,
        "qty_normalization_note": qty_note,
        "price_effect": {
            "type": price_effect_type,
            "units_delta": price_delta,
            "not_causal_elasticity": True,
            "baseline_price_paise": price_base,
            "proposed_price_paise": proposed_price_paise,
        },
        "data_source": "SIMULATED_SUPPLY",
        "explanation": (
            f"Forecast-based simulation (baseline p50≈{p50_base:.1f}, proposed p50≈{p50:.1f} u/day). "
            f"Price effect: {price_effect_type} (observational — not causal elasticity). "
            f"Qty: requested {requested_qty} → applied {reorder_qty} ({qty_note}). "
            "Risk probabilities trained on SIMULATED_SUPPLY trajectories."
        ),
    }
