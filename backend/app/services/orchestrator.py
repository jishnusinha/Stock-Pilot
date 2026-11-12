"""Decision DAG orchestrator."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import sqlite3

from app.agents.base import PROVENANCE_SYNTHETIC, new_trace_id
from app.agents.registry import get_agent
from app.core.config import settings
from app.db import repositories as repo
from app.services.reorder_optimizer import OptimizeInput, optimize_reorder
from app.services.trace_writer import TraceWriter


def _explanation(product: dict, opt, agents: dict[str, Any]) -> dict:
    lines = [
        f"SKU {product['sku']}: current stock {product['stock_on_hand']} units.",
        f"Median demand forecast {agents.get('p50_units', 0):.1f} u/day.",
    ]
    if agents.get("is_anomaly"):
        lines.append("Recent sales pattern flagged as anomalous — forecast confidence reduced.")
    if agents.get("p_zero_demand", 0) > 0.35:
        lines.append("Intermittent demand detected; safety stock bias applied.")
    lines.extend(opt.rationale)
    return {"summary": " ".join(lines[:2]), "bullets": lines, "template": "deterministic_v1"}


def run_decision(
    conn: sqlite3.Connection,
    product_id: int,
    *,
    scenario: dict | None = None,
    persist_trace: bool = True,
    budget_paise: int = 500_000,
) -> dict:
    product = repo.get_product(conn, product_id)
    if not product:
        raise ValueError("Product not found")

    trace_id = new_trace_id()
    tw = TraceWriter(conn, trace_id) if persist_trace else None
    ctx_extra = scenario or {}
    provenance = PROVENANCE_SYNTHETIC

    agents_out: dict[str, Any] = {}
    chain = [
        "calendar_effect",
        "price_response",
        "intermittence",
        "sales_anomaly",
        "product_similarity",
    ]
    for name in chain:
        agent = get_agent(name)
        try:
            agent.load()
        except FileNotFoundError:
            continue
        if tw:
            with tw.span(name):
                res = agent.predict(conn, product_id, **ctx_extra)
        else:
            res = agent.predict(conn, product_id, **ctx_extra)
        agents_out[name] = res.output
        if tw:
            tw.record(res)

    demand = get_agent("demand")
    try:
        demand.load()
        d_res = demand.predict(conn, product_id, **ctx_extra)
        p50 = float(d_res.output.get("p50_units", 1.0))
        agents_out["p50_units"] = p50
        if tw:
            tw.record(d_res)
    except FileNotFoundError:
        p50 = 1.0

    interval = get_agent("demand_interval")
    try:
        interval.load()
        i_res = interval.predict(conn, product_id, p50_units=p50, **ctx_extra)
        agents_out.update(i_res.output)
        if tw:
            tw.record(i_res)
    except FileNotFoundError:
        pass

    eta_agent = get_agent("supplier_eta")
    try:
        eta_agent.load()
        eta_res = eta_agent.predict(conn, product_id)
        lead_days = int(eta_res.output.get("lead_days", product.get("base_lead_days", 7)))
        eta_days = float(eta_res.output.get("eta_days", lead_days))
        if tw:
            tw.record(eta_res)
    except FileNotFoundError:
        lead_days = int(product.get("base_lead_days", 7))
        eta_days = float(lead_days)

    order_guess = int(product["pack_size"])

    stockout = get_agent("stockout_risk")
    excess = get_agent("excess_risk")
    so_risk, ex_risk = 0.3, 0.2
    try:
        stockout.load()
        so_res = stockout.predict(
            conn, product_id, eta_days=eta_days, lead_days=lead_days, order_qty=order_guess
        )
        so_risk = float(so_res.output.get("stockout_risk", so_risk))
        if tw:
            tw.record(so_res)
    except FileNotFoundError:
        pass
    try:
        excess.load()
        ex_res = excess.predict(
            conn, product_id, eta_days=eta_days, lead_days=lead_days, order_qty=order_guess
        )
        ex_risk = float(ex_res.output.get("excess_risk", ex_risk))
        if tw:
            tw.record(ex_res)
    except FileNotFoundError:
        pass

    opt = optimize_reorder(
        OptimizeInput(
            stock_on_hand=int(product["stock_on_hand"]),
            daily_demand=max(0.1, p50),
            unit_cost_paise=int(product["unit_cost_paise"]),
            pack_size=int(product["pack_size"]),
            lead_days=lead_days,
            stockout_risk=so_risk,
            excess_risk=ex_risk,
            budget_paise=budget_paise,
            shelf_life_days=product.get("shelf_life_days"),
        )
    )

    as_of = settings.demo_date
    arrival = (datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=lead_days)).strftime("%Y-%m-%d")
    explanation = _explanation(product, opt, agents_out)

    forecast_series = agents_out.get("forecast_series")
    if forecast_series:
        model_version = interval.version if interval.version else "demand_v1"
        series_db = []
        for i, row in enumerate(forecast_series[:28]):
            td = (
                datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=i + 1)
            ).strftime("%Y-%m-%d")
            series_db.append(
                {
                    "target_date": td,
                    "p10_units": row["p10_units"],
                    "p50_units": row["p50_units"],
                    "p90_units": row["p90_units"],
                }
            )
        repo.replace_forecasts(conn, product_id, as_of, model_version, series_db, provenance)

    dos = float(product["stock_on_hand"]) / max(0.1, p50)
    # Combine model risk with inventory cover so seeded low-stock SKUs surface in UI
    if dos <= 7 or so_risk >= 0.55:
        risk_level = "high"
    elif dos <= 21 or so_risk >= 0.3:
        risk_level = "medium"
    else:
        risk_level = "low"
    repo.upsert_risk_cache(
        conn,
        product_id,
        {
            "risk_level": risk_level,
            "days_of_supply": dos,
            "forecast_28d": p50 * 28,
            "sell_through": p50,
            "stockout_risk": so_risk,
            "provenance": provenance,
        },
    )

    result = {
        "product_id": product_id,
        "trace_id": trace_id,
        "suggested_qty": opt.suggested_qty,
        "estimated_cost_paise": opt.estimated_cost_paise,
        "expected_stockout_risk": so_risk,
        "expected_excess_risk": ex_risk,
        "expected_arrival_date": arrival,
        "explanation": explanation,
        "stock_path": opt.stock_path,
        "agents": agents_out,
        "provenance": provenance,
    }

    if persist_trace:
        conn.commit()
    return result
