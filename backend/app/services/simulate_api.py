"""What-if simulation API helper — forecast-based inventory paths."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from app.agents.registry import get_agent
from app.core.config import settings
from app.db import repositories as repo
from app.services.scenarios import ScenarioInput, simulate_stock_path


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
    # Enforce pack multiple & budget
    if pack > 1 and reorder_qty % pack != 0:
        reorder_qty = (reorder_qty // pack) * pack
    max_by_budget = (budget_paise // cost) if cost > 0 else reorder_qty
    reorder_qty = min(reorder_qty, max_by_budget)

    # Demand estimate
    p50 = 1.0
    try:
        demand = get_agent("demand")
        demand.load()
        d_res = demand.predict(
            conn, product_id, proposed_price_paise=proposed_price_paise
        )
        p50 = float(d_res.output.get("p50_units", p50))
    except Exception:
        # fallback: recent mean
        row = conn.execute(
            """
            SELECT AVG(units) FROM sales
            WHERE product_id=? AND sale_date >= date(?, '-28 days')
            """,
            (product_id, settings.demo_date),
        ).fetchone()
        p50 = float(row[0] or 1.0)

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
            ).output.get("stockout_risk", 0.3)
        )
        so_risk_p = float(
            so.predict(
                conn,
                product_id,
                eta_days=lead_time_days,
                lead_days=lead_time_days,
                order_qty=reorder_qty,
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
            ).output.get("excess_risk", 0.1)
        )
    except Exception:
        pass

    base_qty = 0  # current plan: no new order in horizon for comparison
    # Prefer existing open recommendation qty as "current plan" if present
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
            daily_demand_p50=p50,
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

    fulfilled_base = max(0, horizon_days - base_path.stockout_days) * p50
    fulfilled_prop = max(0, horizon_days - prop_path.stockout_days) * p50
    price_base = int(product["selling_price_paise"])
    rev_b = int(fulfilled_base * price_base)
    rev_p = int(fulfilled_prop * proposed_price_paise)
    cost_b = int(base_qty * cost)
    cost_p = int(reorder_qty * cost)
    margin_b = rev_b - cost_b
    margin_p = rev_p - cost_p

    arrival = (as_of + timedelta(days=lead_time_days)).isoformat()

    def fmt_pct(x):
        return f"{100 * x:.1f}%" if x is not None else "N/A"

    comparison = [
        {
            "metric": "Projected revenue",
            "baseline": rev_b,
            "proposed": rev_p,
            "delta": f"{rev_p - rev_b:+d} paise",
        },
        {
            "metric": "Stockout days (path)",
            "baseline": base_path.stockout_days,
            "proposed": prop_path.stockout_days,
            "delta": f"{prop_path.stockout_days - base_path.stockout_days:+d}",
        },
        {
            "metric": "Simulated stockout risk",
            "baseline": fmt_pct(so_risk_b),
            "proposed": fmt_pct(so_risk_p),
            "delta": None,
        },
        {
            "metric": "Purchase cost",
            "baseline": cost_b,
            "proposed": cost_p,
            "delta": f"{cost_p - cost_b:+d} paise",
        },
        {
            "metric": "Gross margin proxy",
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
            "unmet_demand_units": base_path.stockout_days * p50,
            "stockout_probability": so_risk_b,
            "excess_risk_units": None,
            "purchase_cost_paise": cost_b,
            "revenue_paise": rev_b,
            "gross_margin_paise": margin_b,
        },
        "proposed_metrics": {
            "stockout_days": prop_path.stockout_days,
            "unmet_demand_units": prop_path.stockout_days * p50,
            "stockout_probability": so_risk_p,
            "excess_risk_units": ex_risk_p,
            "purchase_cost_paise": cost_p,
            "revenue_paise": rev_p,
            "gross_margin_paise": margin_p,
        },
        "comparison_rows": comparison,
        "arrival_date": arrival,
        "data_source": "SIMULATED_SUPPLY",
        "explanation": (
            f"Forecast-based simulation (p50≈{p50:.1f} u/day). "
            "Risk probabilities trained on SIMULATED_SUPPLY trajectories — not live supplier outcomes."
        ),
    }
