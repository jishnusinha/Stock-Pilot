"""Decision DAG orchestrator with meaningful agent signal flow."""

from __future__ import annotations

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
        lines.append("Recent sales pattern flagged as anomalous — forecast blended toward recent median.")
    if agents.get("p_zero_demand", 0) > 0.35:
        lines.append("Intermittent demand detected; demand forecast shrunk toward zero.")
    if agents.get("price_units_delta"):
        lines.append(
            f"Observational price-response delta applied: {agents['price_units_delta']:+.2f} u/day "
            "(not causal elasticity)."
        )
    if agents.get("calendar_uplift"):
        lines.append(f"Calendar uplift applied: {agents['calendar_uplift']:+.2f} u/day.")
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
    ctx_extra = dict(scenario or {})
    provenance = PROVENANCE_SYNTHETIC
    notices: list[str] = []

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
            notices.append(f"{name}: artifact missing — skipped")
            continue
        try:
            if tw:
                with tw.span(name):
                    res = agent.predict(conn, product_id, **ctx_extra)
            else:
                res = agent.predict(conn, product_id, **ctx_extra)
            agents_out[name] = res.output
            if tw:
                tw.record(res)
        except Exception as exc:  # explicit failure, not silent pass
            notices.append(f"{name}: {type(exc).__name__}: {exc}")
            agents_out[name] = {"status": "error", "error": str(exc)}

    # Flatten upstream signals for demand conditioning
    cal = agents_out.get("calendar_effect") or {}
    price = agents_out.get("price_response") or {}
    inter = agents_out.get("intermittence") or {}
    anom = agents_out.get("sales_anomaly") or {}
    sim = agents_out.get("product_similarity") or {}

    demand_kwargs = {
        **ctx_extra,
        "calendar_uplift": float(cal.get("calendar_uplift") or 0.0),
        "price_units_delta": float(price.get("expected_units_delta") or 0.0),
        "p_zero_demand": float(inter.get("p_zero_demand") or 0.0),
        "is_anomaly": bool(anom.get("is_anomaly", False)),
        "similarity_demand": sim.get("similarity_demand"),
    }
    agents_out["calendar_uplift"] = demand_kwargs["calendar_uplift"]
    agents_out["price_units_delta"] = demand_kwargs["price_units_delta"]
    agents_out["p_zero_demand"] = demand_kwargs["p_zero_demand"]
    agents_out["is_anomaly"] = demand_kwargs["is_anomaly"]

    demand = get_agent("demand")
    p50 = 1.0
    try:
        demand.load()
        if tw:
            with tw.span("demand"):
                d_res = demand.predict(conn, product_id, **demand_kwargs)
        else:
            d_res = demand.predict(conn, product_id, **demand_kwargs)
        p50 = float(d_res.output.get("p50_units", 1.0))
        agents_out["p50_units"] = p50
        agents_out["demand"] = d_res.output
        if tw:
            tw.record(d_res)
    except FileNotFoundError:
        notices.append("demand: artifact missing — using fallback 1.0")
        p50 = 1.0

    p10, p90 = p50 * 0.7, p50 * 1.3
    interval = get_agent("demand_interval")
    try:
        interval.load()
        if tw:
            with tw.span("demand_interval"):
                i_res = interval.predict(conn, product_id, p50_units=p50, **ctx_extra)
        else:
            i_res = interval.predict(conn, product_id, p50_units=p50, **ctx_extra)
        agents_out.update(i_res.output)
        p10 = float(i_res.output.get("p10_units", p10))
        p90 = float(i_res.output.get("p90_units", p90))
        if tw:
            tw.record(i_res)
    except FileNotFoundError:
        notices.append("demand_interval: artifact missing")

    eta_agent = get_agent("supplier_eta")
    try:
        eta_agent.load()
        if tw:
            with tw.span("supplier_eta"):
                eta_res = eta_agent.predict(conn, product_id)
        else:
            eta_res = eta_agent.predict(conn, product_id)
        lead_days = int(eta_res.output.get("lead_days", product.get("base_lead_days", 7)))
        eta_days = float(eta_res.output.get("eta_days", lead_days))
        if tw:
            tw.record(eta_res)
        agents_out["supplier_eta"] = eta_res.output
    except FileNotFoundError:
        lead_days = int(product.get("base_lead_days", 7))
        eta_days = float(lead_days)
        notices.append("supplier_eta: artifact missing — using base lead days")

    stockout = get_agent("stockout_risk")
    excess = get_agent("excess_risk")
    so_loaded = ex_loaded = False
    try:
        stockout.load()
        so_loaded = True
    except FileNotFoundError:
        notices.append("stockout_risk: artifact missing")
    try:
        excess.load()
        ex_loaded = True
    except FileNotFoundError:
        notices.append("excess_risk: artifact missing")

    def risk_fn(qty: int) -> tuple[float, float]:
        so_r, ex_r = 0.3, 0.2
        if so_loaded:
            so_r = float(
                stockout.predict(
                    conn,
                    product_id,
                    eta_days=eta_days,
                    lead_days=lead_days,
                    order_qty=qty,
                    daily_demand=p50,
                    demand_p90=p90,
                ).output.get("stockout_risk", so_r)
            )
        if ex_loaded:
            ex_r = float(
                excess.predict(
                    conn,
                    product_id,
                    eta_days=eta_days,
                    lead_days=lead_days,
                    order_qty=qty,
                    daily_demand=p50,
                    demand_p90=p90,
                ).output.get("excess_risk", ex_r)
            )
        return so_r, ex_r

    # Baseline risks at one-pack guess for reporting
    so_risk, ex_risk = risk_fn(int(product["pack_size"]))
    if tw and so_loaded:
        tw.record(
            stockout.predict(
                conn,
                product_id,
                eta_days=eta_days,
                lead_days=lead_days,
                order_qty=int(product["pack_size"]),
                daily_demand=p50,
                demand_p90=p90,
            )
        )
    if tw and ex_loaded:
        tw.record(
            excess.predict(
                conn,
                product_id,
                eta_days=eta_days,
                lead_days=lead_days,
                order_qty=int(product["pack_size"]),
                daily_demand=p50,
                demand_p90=p90,
            )
        )

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
            risk_fn=risk_fn if (so_loaded or ex_loaded) else None,
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
        "notices": notices,
        "signal_flow": {
            "calendar_uplift": demand_kwargs["calendar_uplift"],
            "price_units_delta": demand_kwargs["price_units_delta"],
            "p_zero_demand": demand_kwargs["p_zero_demand"],
            "is_anomaly": demand_kwargs["is_anomaly"],
            "similarity_demand": demand_kwargs["similarity_demand"],
            "eta_days": eta_days,
            "demand_p50": p50,
            "demand_p90": p90,
            "optimizer_used_candidate_risks": bool(so_loaded or ex_loaded),
        },
    }

    if persist_trace:
        conn.commit()
    return result
