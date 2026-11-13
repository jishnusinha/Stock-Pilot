"""Predictive inventory analytics over persisted forecasts, risk cache, and recommendations.

Does not train models. Does not invent missing daily forecasts. Historical date filters
select the descriptive cohort (category/supplier/product/ABC cell); predictive as-of
comes from the forecast origin date.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Literal

from app.core.config import settings
from app.services import inventory_analytics as ia
from app.services.inventory_projection import (
    ReceiptEvent,
    day_index_for_date,
    project_inventory_path,
)

Horizon = Literal[7, 14, 28]
Mode = Literal["no_reorder", "recommended", "scenario"]

STOCKOUT_HIGH = 0.55
STOCKOUT_MODERATE = 0.30
EXCESS_COVER_DAYS = ia.EXCESS_COVER_DAYS

INTERVAL_NOTE = (
    "Per-SKU p10–p90 come from the Demand Interval Agent (quantile GBR). "
    "Portfolio bands sum SKU quantiles as a heuristic total-units range — "
    "not a calibrated joint quantile or 95% confidence interval."
)
PROJECTION_NOTE = (
    "Inventory paths are deterministic simulations driven by forecast p50 demand "
    "and dated receipts. A demand interval is not automatically a calibrated "
    "inventory probability band."
)
FRESHNESS_NOTE = (
    "Demand forecasts remain valid after stock changes; stockout-risk cache and "
    "inventory projections must reflect current on-hand stock."
)


def _horizon(days: int | None) -> Horizon:
    if days in (7, 14, 28):
        return days  # type: ignore[return-value]
    return 28


def _mode(raw: str | None) -> Mode:
    if raw in ("no_reorder", "recommended", "scenario"):
        return raw  # type: ignore[return-value]
    return "no_reorder"


def _product_rows(conn: sqlite3.Connection, filters: ia.Filters) -> list[dict]:
    ia._assert_entities(conn, filters)
    where, params = ia._product_where(filters, conn=conn)
    rows = conn.execute(
        f"""
        SELECT p.id AS product_id, p.sku, p.name, p.category, p.supplier_id,
               p.stock_on_hand, p.unit_cost_paise, p.pack_size, p.shelf_life_days,
               r.risk_level, r.days_of_supply, r.forecast_28d, r.sell_through,
               r.stockout_risk, r.updated_at AS risk_updated_at, r.provenance AS risk_provenance
        FROM products p
        LEFT JOIN product_risk_cache r ON r.product_id = p.id
        WHERE {where}
        ORDER BY p.id
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _forecast_meta(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT as_of_date, model_version, COUNT(*) AS n_rows,
               COUNT(DISTINCT product_id) AS n_products,
               MIN(target_date) AS first_target, MAX(target_date) AS last_target
        FROM forecasts
        WHERE as_of_date = (SELECT MAX(as_of_date) FROM forecasts)
        """
    ).fetchone()
    if row is None or row["as_of_date"] is None:
        return {
            "as_of_date": None,
            "model_version": None,
            "n_rows": 0,
            "n_products": 0,
            "first_target": None,
            "last_target": None,
            "available_horizon_days": 0,
            "source": "forecasts",
            "agent": "demand_interval",
        }
    first = row["first_target"]
    last = row["last_target"]
    horizon = 0
    if first and last:
        horizon = (datetime.fromisoformat(last) - datetime.fromisoformat(first)).days + 1
    return {
        "as_of_date": row["as_of_date"],
        "model_version": row["model_version"],
        "n_rows": int(row["n_rows"] or 0),
        "n_products": int(row["n_products"] or 0),
        "first_target": first,
        "last_target": last,
        "available_horizon_days": horizon,
        "source": "forecasts",
        "agent": "demand_interval",
    }


def _forecast_map(
    conn: sqlite3.Connection, product_ids: list[int], as_of: str | None
) -> dict[int, list[dict]]:
    if not product_ids or not as_of:
        return {}
    marks = ",".join("?" * len(product_ids))
    rows = conn.execute(
        f"""
        SELECT product_id, target_date, p10_units, p50_units, p90_units, model_version, provenance
        FROM forecasts
        WHERE as_of_date = ? AND product_id IN ({marks})
        ORDER BY product_id, target_date
        """,
        [as_of, *product_ids],
    ).fetchall()
    out: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        out[int(row["product_id"])].append(dict(row))
    return out


def _open_recommendations(conn: sqlite3.Connection, product_ids: list[int]) -> dict[int, dict]:
    if not product_ids:
        return {}
    marks = ",".join("?" * len(product_ids))
    rows = conn.execute(
        f"""
        SELECT r.*
        FROM recommendations r
        WHERE r.product_id IN ({marks})
          AND r.status IN ('open', 'proposed')
          AND r.id = (
            SELECT MAX(r2.id) FROM recommendations r2
            WHERE r2.product_id = r.product_id AND r2.status IN ('open', 'proposed')
          )
        """,
        product_ids,
    ).fetchall()
    return {int(row["product_id"]): dict(row) for row in rows}


def _approved_receipts(conn: sqlite3.Connection, product_ids: list[int]) -> dict[int, list[dict]]:
    """Pending/approved reorders that have a stored expected arrival date."""
    if not product_ids:
        return {}
    marks = ",".join("?" * len(product_ids))
    rows = conn.execute(
        f"""
        SELECT o.id, o.product_id, o.qty, o.status, r.expected_arrival_date
        FROM reorders o
        LEFT JOIN recommendations r ON r.id = o.recommendation_id
        WHERE o.product_id IN ({marks})
          AND o.status IN ('pending', 'approved')
          AND r.expected_arrival_date IS NOT NULL
        """,
        product_ids,
    ).fetchall()
    out: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        out[int(row["product_id"])].append(dict(row))
    return out


def _sum_horizon(series: list[dict], horizon: int, key: str = "p50_units") -> float | None:
    if not series:
        return None
    chunk = series[:horizon]
    if len(chunk) < horizon:
        return None
    return float(sum(float(row[key] or 0) for row in chunk))


def _risk_freshness(row: dict) -> str:
    prov = str(row.get("risk_provenance") or "")
    if "STALE" in prov.upper():
        return "stale"
    if row.get("stockout_risk") is None and row.get("risk_level") is None:
        return "unavailable"
    return "current"


def _prediction_freshness(meta: dict[str, Any], products: list[dict], covered: int) -> dict[str, Any]:
    as_of = meta.get("as_of_date")
    demo = settings.demo_date
    stale_risk = sum(1 for p in products if _risk_freshness(p) == "stale")
    if not as_of or meta.get("n_rows", 0) == 0:
        status = "unavailable"
    elif covered == 0:
        status = "unavailable"
    elif covered < len(products):
        status = "partial"
    elif as_of != demo:
        status = "stale"
    elif stale_risk:
        status = "partial"
    else:
        status = "current"
    return {
        "status": status,
        "forecast_as_of": as_of,
        "operational_as_of": demo,
        "stale_risk_count": stale_risk,
        "note": FRESHNESS_NOTE,
    }


def _band(prob: float | None) -> str | None:
    if prob is None:
        return None
    if prob >= STOCKOUT_HIGH:
        return "high"
    if prob >= STOCKOUT_MODERATE:
        return "moderate"
    return "low"


def overview(
    conn: sqlite3.Connection,
    filters: ia.Filters,
    *,
    horizon_days: int | None = 28,
) -> dict[str, Any]:
    horizon = _horizon(horizon_days)
    products = _product_rows(conn, filters)
    meta = _forecast_meta(conn)
    as_of = meta.get("as_of_date")
    ids = [int(p["product_id"]) for p in products]
    forecasts = _forecast_map(conn, ids, as_of)
    recs = _open_recommendations(conn, ids)

    demand_7 = demand_14 = demand_28 = 0.0
    have_7 = have_14 = have_28 = True
    covered = 0
    for pid in ids:
        series = forecasts.get(pid, [])
        if series:
            covered += 1
        s7 = _sum_horizon(series, 7)
        s14 = _sum_horizon(series, 14)
        s28 = _sum_horizon(series, 28)
        if s7 is None:
            have_7 = False
        else:
            demand_7 += s7
        if s14 is None:
            have_14 = False
        else:
            demand_14 += s14
        if s28 is None:
            have_28 = False
        else:
            demand_28 += s28

    at_risk = sum(
        1
        for p in products
        if p.get("stockout_risk") is not None and float(p["stockout_risk"]) >= STOCKOUT_HIGH
    )
    operational_high = sum(1 for p in products if str(p.get("risk_level") or "") == "high")
    excess_proxy = ia._excess(conn, filters)
    replenishment = sum(
        int(recs[pid]["estimated_cost_paise"] or 0)
        for pid in ids
        if pid in recs and int(recs[pid].get("suggested_qty") or 0) > 0
    )

    projected = inventory_projection(
        conn,
        filters,
        horizon_days=horizon,
        mode="no_reorder",
    )
    end_value = None
    if projected.get("ready") and projected.get("series"):
        end_value = projected["series"][-1].get("projected_inventory_value_paise")

    freshness = _prediction_freshness(meta, products, covered)
    live_units, live_value = ia._live(conn, filters)

    return {
        "ready": bool(as_of and covered > 0),
        "horizon_days": horizon,
        "forecast_as_of": as_of,
        "operational_as_of": settings.demo_date,
        "model_version": meta.get("model_version"),
        "forecast_source": "demand_interval.forecasts",
        "available_horizon_days": meta.get("available_horizon_days"),
        "product_count": len(products),
        "forecast_coverage": {"covered": covered, "selected": len(products)},
        "freshness": freshness,
        "interval_note": INTERVAL_NOTE,
        "projection_note": PROJECTION_NOTE,
        "kpis": {
            "expected_demand_units": {
                "horizon_days": horizon,
                "value": {7: demand_7 if have_7 else None, 14: demand_14 if have_14 else None, 28: demand_28 if have_28 else None}.get(
                    horizon
                ),
                "by_horizon": {
                    "7": demand_7 if have_7 else None,
                    "14": demand_14 if have_14 else None,
                    "28": demand_28 if have_28 else None,
                },
                "label": f"Expected demand · Next {horizon} days",
                "unavailable_reason": None
                if {7: have_7, 14: have_14, 28: have_28}[horizon]
                else "Fewer daily forecast rows than the selected horizon.",
            },
            "products_at_stockout_risk": {
                "value": at_risk,
                "threshold": STOCKOUT_HIGH,
                "definition": f"Count of SKUs with modeled stockout_risk ≥ {STOCKOUT_HIGH:.0%} (not a summed probability).",
                "operational_high_risk_level_count": operational_high,
                "operational_note": (
                    "product_risk_cache.risk_level=high also includes short days-of-supply "
                    f"(≤7) even when probability is below {STOCKOUT_HIGH:.0%}."
                ),
            },
            "excess_inventory_value_paise": {
                "value": excess_proxy,
                "kind": "forecast_cover_proxy",
                "definition": ia.EXCESS_DEFINITION,
                "distinct_from": "recommendations.expected_excess_risk (Excess Risk Agent probability)",
            },
            "recommended_replenishment_spend_paise": {
                "value": replenishment,
                "definition": "Sum of estimated_cost_paise for open recommendations with suggested_qty > 0.",
            },
            "projected_inventory_value_paise": {
                "value": end_value,
                "policy": "no_reorder",
                "horizon_days": horizon,
                "definition": "Period-end projected value under no new purchase orders (approved dated receipts only).",
                "current_inventory_value_paise": live_value,
            },
            "forecast_coverage": {
                "covered": covered,
                "selected": len(products),
                "label": f"{covered} / {len(products)} SKUs covered",
            },
        },
        "live_stock_units": live_units,
        "live_inventory_value_paise": live_value,
        "provenance": "SYNTHETIC_DEMO",
    }


def demand_outlook(
    conn: sqlite3.Connection,
    filters: ia.Filters,
    *,
    horizon_days: int | None = 28,
    history_days: int = 28,
) -> dict[str, Any]:
    horizon = _horizon(horizon_days)
    products = _product_rows(conn, filters)
    meta = _forecast_meta(conn)
    as_of = meta.get("as_of_date")
    ids = [int(p["product_id"]) for p in products]
    forecasts = _forecast_map(conn, ids, as_of)
    covered = sum(1 for pid in ids if forecasts.get(pid))

    history: list[dict] = []
    if as_of and ids:
        start = (datetime.fromisoformat(as_of) - timedelta(days=history_days)).date().isoformat()
        marks = ",".join("?" * len(ids))
        hist_rows = conn.execute(
            f"""
            SELECT sale_date AS d, SUM(units) AS u
            FROM sales
            WHERE sale_date >= ? AND sale_date <= ? AND product_id IN ({marks})
            GROUP BY sale_date
            ORDER BY sale_date
            """,
            [start, as_of, *ids],
        ).fetchall()
        history = [
            {
                "date": row["d"],
                "actual_units": float(row["u"] or 0),
                "p10": None,
                "p50": None,
                "p90": None,
                "is_forecast": False,
            }
            for row in hist_rows
        ]

    by_date: dict[str, dict[str, float]] = defaultdict(lambda: {"p10": 0.0, "p50": 0.0, "p90": 0.0, "n": 0})
    for pid in ids:
        series = forecasts.get(pid, [])[:horizon]
        for row in series:
            bucket = by_date[str(row["target_date"])]
            bucket["p10"] += float(row["p10_units"] or 0)
            bucket["p50"] += float(row["p50_units"] or 0)
            bucket["p90"] += float(row["p90_units"] or 0)
            bucket["n"] += 1

    future = [
        {
            "date": date,
            "actual_units": None,
            "p10": vals["p10"],
            "p50": vals["p50"],
            "p90": vals["p90"],
            "is_forecast": True,
            "sku_count": int(vals["n"]),
            "interval_kind": "sum_of_sku_quantiles_heuristic",
        }
        for date, vals in sorted(by_date.items())
    ]

    single_product = filters.product_id is not None and len(ids) == 1
    return {
        "ready": bool(as_of and covered > 0),
        "forecast_as_of": as_of,
        "operational_as_of": settings.demo_date,
        "horizon_days": horizon,
        "model_version": meta.get("model_version"),
        "forecast_coverage": {"covered": covered, "selected": len(products)},
        "freshness": _prediction_freshness(meta, products, covered),
        "history": history,
        "forecast": future,
        "series": history + future,
        "interval_note": INTERVAL_NOTE
        if not single_product
        else "SKU-level p10–p90 from Demand Interval Agent. Nominal training target ≈ 80% coverage, not 95%.",
        "aggregation": "product" if single_product else "cohort_sum",
        "provenance": "SYNTHETIC_DEMO",
        "source_agents": ["demand", "demand_interval"],
    }


def inventory_projection(
    conn: sqlite3.Connection,
    filters: ia.Filters,
    *,
    horizon_days: int | None = 28,
    mode: str | None = "no_reorder",
    scenario_order_qty: int | None = None,
    scenario_lead_days: int | None = None,
    scenario_product_id: int | None = None,
) -> dict[str, Any]:
    horizon = _horizon(horizon_days)
    mode_name = _mode(mode)
    products = _product_rows(conn, filters)
    meta = _forecast_meta(conn)
    as_of = meta.get("as_of_date")
    if not as_of or not products:
        return {
            "ready": False,
            "forecast_as_of": as_of,
            "mode": mode_name,
            "horizon_days": horizon,
            "series": [],
            "note": "No forecasts available for projection.",
            "provenance": "SYNTHETIC_DEMO",
        }

    ids = [int(p["product_id"]) for p in products]
    forecasts = _forecast_map(conn, ids, as_of)
    recs = _open_recommendations(conn, ids)
    approved = _approved_receipts(conn, ids)
    covered = sum(1 for pid in ids if len(forecasts.get(pid, [])) >= horizon)
    if covered == 0:
        return {
            "ready": False,
            "forecast_as_of": as_of,
            "mode": mode_name,
            "horizon_days": horizon,
            "series": [],
            "note": "Selected products lack a full daily forecast for this horizon.",
            "provenance": "SYNTHETIC_DEMO",
        }

    # Aggregate path by summing SKU closing values / units each day
    agg: dict[str, dict[str, float]] = {}
    total_unmet = 0.0
    total_receipts = 0.0
    stockout_sku_days = 0
    notes: list[str] = [PROJECTION_NOTE]
    sku_details: list[dict] = []

    for product in products:
        pid = int(product["product_id"])
        series = forecasts.get(pid, [])[:horizon]
        if len(series) < horizon:
            continue
        demand = [float(row["p50_units"] or 0) for row in series]
        receipts: list[ReceiptEvent] = []

        for order in approved.get(pid, []):
            idx = day_index_for_date(as_of, order["expected_arrival_date"], horizon)
            if idx is None:
                continue
            receipts.append(
                ReceiptEvent(
                    day_index=idx,
                    qty=float(order["qty"]),
                    source="approved_reorder",
                    date_role="predicted",
                )
            )

        if mode_name == "recommended":
            rec = recs.get(pid)
            if rec and int(rec.get("suggested_qty") or 0) > 0 and rec.get("expected_arrival_date"):
                idx = day_index_for_date(as_of, rec["expected_arrival_date"], horizon)
                if idx is not None:
                    receipts.append(
                        ReceiptEvent(
                            day_index=idx,
                            qty=float(rec["suggested_qty"]),
                            source="recommended",
                            date_role="predicted",
                        )
                    )
                else:
                    notes.append(
                        f"Recommendation for {product['sku']} has arrival outside the {horizon}-day window."
                    )
            elif rec and int(rec.get("suggested_qty") or 0) > 0:
                notes.append(
                    f"Recommendation for {product['sku']} has no expected_arrival_date; qty was not applied."
                )

        if mode_name == "scenario":
            target_pid = scenario_product_id or filters.product_id
            if target_pid is not None and pid == int(target_pid):
                qty = int(scenario_order_qty or 0)
                lead = int(scenario_lead_days or 0)
                if qty > 0 and 1 <= lead <= horizon:
                    receipts.append(
                        ReceiptEvent(
                            day_index=lead,
                            qty=float(qty),
                            source="scenario",
                            date_role="predicted",
                        )
                    )

        path = project_inventory_path(
            opening_stock=float(product["stock_on_hand"]),
            unit_cost_paise=int(product["unit_cost_paise"]),
            as_of_date=as_of,
            daily_demand=demand,
            receipts=receipts,
            mode=mode_name,
            model_version=meta.get("model_version"),
        )
        total_unmet += path.unmet_demand_units
        total_receipts += path.total_receipts
        stockout_sku_days += path.stockout_days
        sku_details.append(
            {
                "product_id": pid,
                "sku": product["sku"],
                "ending_stock": path.ending_stock,
                "ending_value_paise": path.ending_value_paise,
                "unmet_demand_units": path.unmet_demand_units,
                "stockout_days": path.stockout_days,
            }
        )
        for day in path.days:
            bucket = agg.setdefault(
                day.date,
                {
                    "projected_inventory_units": 0.0,
                    "projected_inventory_value_paise": 0.0,
                    "predicted_demand": 0.0,
                    "fulfilled_units": 0.0,
                    "receipts": 0.0,
                    "unmet_demand": 0.0,
                },
            )
            bucket["projected_inventory_units"] += day.closing_stock
            bucket["projected_inventory_value_paise"] += day.closing_value_paise
            bucket["predicted_demand"] += day.predicted_demand
            bucket["fulfilled_units"] += day.fulfilled_units
            bucket["receipts"] += day.receipts
            bucket["unmet_demand"] += day.unmet_demand

    # Optional recent historical inventory value for chart continuity
    history = _recent_inventory_history(conn, filters, as_of, days=14)

    series = []
    for date, vals in sorted(agg.items()):
        series.append(
            {
                "date": date,
                "is_forecast": True,
                "projected_inventory_units": vals["projected_inventory_units"],
                "projected_inventory_value_paise": int(round(vals["projected_inventory_value_paise"])),
                "predicted_demand": vals["predicted_demand"],
                "fulfilled_units": vals["fulfilled_units"],
                "receipts": vals["receipts"],
                "unmet_demand": vals["unmet_demand"],
                "scenario": mode_name,
                "model_version": meta.get("model_version"),
                "forecast_as_of": as_of,
            }
        )

    live_units, live_value = ia._live(conn, filters)
    return {
        "ready": True,
        "forecast_as_of": as_of,
        "operational_as_of": settings.demo_date,
        "mode": mode_name,
        "horizon_days": horizon,
        "model_version": meta.get("model_version"),
        "forecast_coverage": {"covered": covered, "selected": len(products)},
        "freshness": _prediction_freshness(meta, products, covered),
        "opening_stock_units": live_units,
        "opening_inventory_value_paise": live_value,
        "ending_stock_units": series[-1]["projected_inventory_units"] if series else live_units,
        "ending_inventory_value_paise": series[-1]["projected_inventory_value_paise"] if series else live_value,
        "total_unmet_demand_units": total_unmet,
        "total_receipts": total_receipts,
        "stockout_sku_days": stockout_sku_days,
        "history": history,
        "series": series,
        "comparison_hint": "Request mode=recommended for the optimizer path, or mode=scenario with qty/lead.",
        "projection_note": PROJECTION_NOTE,
        "notes": sorted(set(notes))[:12],
        "sku_sample": sku_details[:12],
        "provenance": "SYNTHETIC_DEMO",
        "source_agents": ["demand_interval", "supplier_eta"],
    }


def _recent_inventory_history(
    conn: sqlite3.Connection, filters: ia.Filters, as_of: str, *, days: int
) -> list[dict]:
    run = ia._latest_run(conn)
    if run is None:
        return []
    start = (datetime.fromisoformat(as_of) - timedelta(days=days)).date().isoformat()
    where, params = ia._where(filters, int(run["id"]), conn=conn)
    rows = conn.execute(
        f"""
        SELECT s.snapshot_date AS date,
               SUM(s.closing_stock) AS units,
               SUM(s.closing_value_paise) AS value_paise
        FROM inventory_daily_snapshots s
        JOIN products p ON p.id = s.product_id
        WHERE {where} AND s.snapshot_date >= ? AND s.snapshot_date <= ?
        GROUP BY s.snapshot_date
        ORDER BY s.snapshot_date
        """,
        [*params, start, as_of],
    ).fetchall()
    return [
        {
            "date": row["date"],
            "is_forecast": False,
            "projected_inventory_units": float(row["units"] or 0),
            "projected_inventory_value_paise": int(row["value_paise"] or 0),
            "scenario": "historical",
            "label": "Observed / reconstructed",
        }
        for row in rows
    ]


def risks(
    conn: sqlite3.Connection,
    filters: ia.Filters,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    products = _product_rows(conn, filters)
    meta = _forecast_meta(conn)
    as_of = meta.get("as_of_date")
    ids = [int(p["product_id"]) for p in products]
    forecasts = _forecast_map(conn, ids, as_of)
    recs = _open_recommendations(conn, ids)
    covered = sum(1 for pid in ids if forecasts.get(pid))

    bands = {"low": 0, "moderate": 0, "high": 0, "unavailable": 0}
    by_category: dict[str, dict[str, Any]] = {}
    ranking: list[dict] = []

    for product in products:
        pid = int(product["product_id"])
        prob = product.get("stockout_risk")
        band = _band(None if prob is None else float(prob))
        if band is None:
            bands["unavailable"] += 1
        else:
            bands[band] += 1
        cat = product["category"] or "Unknown"
        cat_row = by_category.setdefault(
            cat,
            {"category": cat, "at_risk_skus": 0, "sku_count": 0, "stock_value_paise": 0, "avg_days_of_supply": []},
        )
        cat_row["sku_count"] += 1
        cat_row["stock_value_paise"] += int(product["stock_on_hand"]) * int(product["unit_cost_paise"])
        if product.get("days_of_supply") is not None:
            cat_row["avg_days_of_supply"].append(float(product["days_of_supply"]))
        if band == "high":
            cat_row["at_risk_skus"] += 1

        series = forecasts.get(pid, [])
        demand_28 = _sum_horizon(series, 28)
        rec = recs.get(pid)
        cache_level = str(product.get("risk_level") or "unavailable")
        ranking.append(
            {
                "product_id": pid,
                "sku": product["sku"],
                "name": product["name"],
                "category": product["category"],
                "current_stock": int(product["stock_on_hand"]),
                "stock_value_paise": int(product["stock_on_hand"]) * int(product["unit_cost_paise"]),
                "forecast_demand_28d": demand_28,
                "stockout_risk": None if prob is None else float(prob),
                "risk_band": band or "unavailable",
                "cache_risk_level": cache_level,
                "days_of_supply": product.get("days_of_supply"),
                "risk_freshness": _risk_freshness(product),
                "suggested_qty": int(rec["suggested_qty"]) if rec else None,
                "estimated_cost_paise": int(rec["estimated_cost_paise"]) if rec and rec.get("estimated_cost_paise") is not None else None,
                "expected_arrival_date": rec.get("expected_arrival_date") if rec else None,
                "trace_id": rec.get("trace_id") if rec else None,
                "excess_risk": float(rec["expected_excess_risk"]) if rec and rec.get("expected_excess_risk") is not None else None,
            }
        )

    ranking.sort(
        key=lambda row: (
            0 if row["risk_band"] == "high" or row["cache_risk_level"] == "high" else 1 if row["risk_band"] == "moderate" or row["cache_risk_level"] == "medium" else 2,
            -(row["stockout_risk"] or 0),
            row["days_of_supply"] if row["days_of_supply"] is not None else 9999,
        )
    )

    categories = []
    for cat_row in by_category.values():
        dos = cat_row.pop("avg_days_of_supply")
        cat_row["avg_days_of_supply"] = (sum(dos) / len(dos)) if dos else None
        categories.append(cat_row)
    categories.sort(key=lambda row: (-row["at_risk_skus"], -row["stock_value_paise"]))

    # Excess ranking (value proxy + modeled risk where available)
    excess_items = []
    for product in products:
        forecast = product.get("forecast_28d")
        if forecast is None or float(forecast) <= 0:
            continue
        daily = float(forecast) / 28.0
        excess_units = max(0.0, float(product["stock_on_hand"]) - daily * EXCESS_COVER_DAYS)
        if excess_units <= 0 and not recs.get(int(product["product_id"])):
            continue
        rec = recs.get(int(product["product_id"]))
        excess_items.append(
            {
                "product_id": int(product["product_id"]),
                "sku": product["sku"],
                "name": product["name"],
                "category": product["category"],
                "current_stock": int(product["stock_on_hand"]),
                "excess_units_proxy": excess_units,
                "excess_value_paise_proxy": int(round(excess_units * int(product["unit_cost_paise"]))),
                "days_of_supply": product.get("days_of_supply"),
                "modeled_excess_risk": float(rec["expected_excess_risk"])
                if rec and rec.get("expected_excess_risk") is not None
                else None,
                "forecast_28d": float(forecast),
            }
        )
    excess_items.sort(key=lambda row: (-row["excess_value_paise_proxy"], -(row["modeled_excess_risk"] or 0)))

    return {
        "ready": True,
        "forecast_as_of": as_of,
        "operational_as_of": settings.demo_date,
        "model_version": meta.get("model_version"),
        "freshness": _prediction_freshness(meta, products, covered),
        "thresholds": {
            "high": STOCKOUT_HIGH,
            "moderate": STOCKOUT_MODERATE,
            "definition": (
                f"high ≥ {STOCKOUT_HIGH:.0%}, moderate ≥ {STOCKOUT_MODERATE:.0%} "
                "(aligned with product_risk_cache risk_level rules)."
            ),
        },
        "distribution": bands,
        "at_risk_count": bands["high"],
        "operational_high_risk_level_count": sum(
            1 for p in products if str(p.get("risk_level") or "") == "high"
        ),
        "categories": categories,
        "products": ranking[: max(1, min(limit, 100))],
        "excess": {
            "items": excess_items[: max(1, min(limit, 100))],
            "proxy_definition": ia.EXCESS_DEFINITION,
            "modeled_risk_definition": (
                "expected_excess_risk from Excess Risk Agent at decision time, stored on recommendations. "
                "Not combined into a composite probability with the cover proxy."
            ),
        },
        "aggregation_note": "Stockout probabilities are never summed. Counts and rankings only.",
        "provenance": "SIMULATED_SUPPLY|SYNTHETIC_DEMO",
        "source_agents": ["stockout_risk", "excess_risk", "demand_interval", "supplier_eta"],
    }


def recommendations(
    conn: sqlite3.Connection,
    filters: ia.Filters,
    *,
    limit: int = 40,
) -> dict[str, Any]:
    products = _product_rows(conn, filters)
    meta = _forecast_meta(conn)
    as_of = meta.get("as_of_date")
    ids = [int(p["product_id"]) for p in products]
    forecasts = _forecast_map(conn, ids, as_of)
    recs = _open_recommendations(conn, ids)
    by_id = {int(p["product_id"]): p for p in products}

    items: list[dict] = []
    total_spend = 0
    for pid, rec in recs.items():
        product = by_id.get(pid)
        if not product:
            continue
        qty = int(rec.get("suggested_qty") or 0)
        cost = int(rec.get("estimated_cost_paise") or 0)
        if qty > 0:
            total_spend += cost
        series = forecasts.get(pid, [])
        demand_28 = _sum_horizon(series, 28)
        explanation = _deterministic_explanation(product, rec, demand_28)
        items.append(
            {
                "product_id": pid,
                "sku": product["sku"],
                "name": product["name"],
                "category": product["category"],
                "current_stock": int(product["stock_on_hand"]),
                "pack_size": int(product["pack_size"]),
                "suggested_qty": qty,
                "estimated_cost_paise": cost,
                "forecast_demand_28d": demand_28,
                "estimated_daily_demand": float(product["sell_through"])
                if product.get("sell_through") is not None
                else (demand_28 / 28.0 if demand_28 is not None else None),
                "stockout_risk": float(rec["expected_stockout_risk"])
                if rec.get("expected_stockout_risk") is not None
                else product.get("stockout_risk"),
                "excess_risk": float(rec["expected_excess_risk"])
                if rec.get("expected_excess_risk") is not None
                else None,
                "expected_arrival_date": rec.get("expected_arrival_date"),
                "arrival_date_role": "predicted" if rec.get("expected_arrival_date") else "unavailable",
                "days_of_supply": product.get("days_of_supply"),
                "status": rec.get("status"),
                "trace_id": rec.get("trace_id"),
                "constraints": _constraints(product, rec),
                "explanation": explanation,
                "ranking_score_inputs": {
                    "stockout_risk": rec.get("expected_stockout_risk") or product.get("stockout_risk") or 0,
                    "unmet_proxy": max(0.0, (demand_28 or 0) - float(product["stock_on_hand"])),
                    "value_at_risk_paise": int(product["stock_on_hand"]) * int(product["unit_cost_paise"]),
                },
            }
        )

    items.sort(
        key=lambda row: (
            0 if (row["stockout_risk"] or 0) >= STOCKOUT_HIGH else 1,
            -(row["stockout_risk"] or 0),
            -row["ranking_score_inputs"]["unmet_proxy"],
            0 if row["suggested_qty"] > 0 else 1,
        )
    )

    insights = _build_insights(items, products, meta)

    return {
        "ready": bool(items),
        "forecast_as_of": as_of,
        "operational_as_of": settings.demo_date,
        "model_version": meta.get("model_version"),
        "total_recommended_spend_paise": total_spend,
        "ranking_rule": (
            "Priority = elevated stockout_risk first, then unmet-demand proxy "
            "(28d forecast − stock), then whether a positive reorder exists. "
            "Not an opaque AI score."
        ),
        "items": items[: max(1, min(limit, 100))],
        "insights": insights,
        "provenance": "SYNTHETIC_DEMO",
        "source_agents": [
            "demand",
            "demand_interval",
            "supplier_eta",
            "stockout_risk",
            "excess_risk",
            "reorder_optimizer",
        ],
    }


def explain_product(conn: sqlite3.Connection, product_id: int) -> dict[str, Any]:
    filters = ia.Filters(product_id=product_id)
    products = _product_rows(conn, filters)
    if not products:
        raise LookupError(f"Unknown product_id={product_id}")
    product = products[0]
    meta = _forecast_meta(conn)
    as_of = meta.get("as_of_date")
    forecasts = _forecast_map(conn, [product_id], as_of).get(product_id, [])
    rec = _open_recommendations(conn, [product_id]).get(product_id)

    baseline = inventory_projection(conn, filters, horizon_days=28, mode="no_reorder")
    recommended = inventory_projection(conn, filters, horizon_days=28, mode="recommended")

    trace = None
    agents: list[dict] = []
    if rec and rec.get("trace_id"):
        runs = conn.execute(
            """
            SELECT agent_name, model_version, status, started_at, duration_ms,
                   input_summary_json, output_summary_json, provenance
            FROM agent_runs
            WHERE trace_id = ?
            ORDER BY id
            """,
            (rec["trace_id"],),
        ).fetchall()
        for row in runs:
            agents.append(
                {
                    "agent_name": row["agent_name"],
                    "model_version": row["model_version"],
                    "status": row["status"],
                    "started_at": row["started_at"],
                    "duration_ms": row["duration_ms"],
                    "provenance": row["provenance"],
                    "input_summary": _safe_json(row["input_summary_json"]),
                    "output_summary": _safe_json(row["output_summary_json"]),
                }
            )
        trace = {"trace_id": rec["trace_id"], "agents": agents}

    demand_28 = _sum_horizon(forecasts, 28)
    return {
        "ready": True,
        "product": {
            "product_id": product_id,
            "sku": product["sku"],
            "name": product["name"],
            "category": product["category"],
            "stock_on_hand": int(product["stock_on_hand"]),
            "unit_cost_paise": int(product["unit_cost_paise"]),
            "pack_size": int(product["pack_size"]),
            "stockout_risk": product.get("stockout_risk"),
            "days_of_supply": product.get("days_of_supply"),
            "risk_freshness": _risk_freshness(product),
        },
        "forecast_as_of": as_of,
        "model_version": meta.get("model_version"),
        "forecast_series": [
            {
                "date": row["target_date"],
                "p10": float(row["p10_units"]),
                "p50": float(row["p50_units"]),
                "p90": float(row["p90_units"]),
            }
            for row in forecasts
        ],
        "forecast_demand_28d": demand_28,
        "recommendation": None
        if not rec
        else {
            "suggested_qty": int(rec["suggested_qty"]),
            "estimated_cost_paise": rec.get("estimated_cost_paise"),
            "expected_arrival_date": rec.get("expected_arrival_date"),
            "expected_stockout_risk": rec.get("expected_stockout_risk"),
            "expected_excess_risk": rec.get("expected_excess_risk"),
            "trace_id": rec.get("trace_id"),
            "explanation": _deterministic_explanation(product, rec, demand_28),
            "constraints": _constraints(product, rec),
        },
        "comparison": {
            "no_reorder": {
                "ending_inventory_value_paise": baseline.get("ending_inventory_value_paise"),
                "total_unmet_demand_units": baseline.get("total_unmet_demand_units"),
                "series": baseline.get("series"),
            },
            "recommended": {
                "ending_inventory_value_paise": recommended.get("ending_inventory_value_paise"),
                "total_unmet_demand_units": recommended.get("total_unmet_demand_units"),
                "series": recommended.get("series"),
            },
            "label": "Simulated inventory trajectories — not realized outcomes.",
        },
        "trace": trace,
        "links": {
            "simulator": f"/simulator?product={product_id}",
            "agents": f"/agents?trace={rec['trace_id']}" if rec and rec.get("trace_id") else "/agents",
            "inventory": f"/inventory?product={product_id}",
            "performance": "/performance",
        },
        "provenance": "SYNTHETIC_DEMO",
    }


def data_quality(conn: sqlite3.Connection, filters: ia.Filters) -> dict[str, Any]:
    products = _product_rows(conn, filters)
    meta = _forecast_meta(conn)
    as_of = meta.get("as_of_date")
    ids = [int(p["product_id"]) for p in products]
    forecasts = _forecast_map(conn, ids, as_of)
    covered = sum(1 for pid in ids if forecasts.get(pid))
    versions = conn.execute(
        "SELECT agent_name, version, trained_at, training_source FROM model_versions ORDER BY agent_name"
    ).fetchall()
    run = ia._latest_run(conn)
    hist_meta = ia._run_meta(run, ready=run is not None and run["status"] == "complete", conn=conn)
    stale_risk = sum(1 for p in products if _risk_freshness(p) == "stale")

    return {
        "ready": True,
        "forecast": meta,
        "forecast_coverage": {"covered": covered, "selected": len(products)},
        "freshness": _prediction_freshness(meta, products, covered),
        "model_versions": [dict(row) for row in versions],
        "historical_analytics": hist_meta,
        "stale_risk_count": stale_risk,
        "limitations": [
            "Demand Interval daily series is flat across the 28-day horizon (same quantiles each day).",
            "Demand Agent Dow-shaped daily_p50 is not persisted in forecasts.",
            "product_risk_cache does not store excess_risk; use recommendations for modeled excess probability.",
            "Portfolio p10–p90 is a sum-of-SKU heuristic, not a joint distribution.",
            "GET predictive endpoints never retrain models.",
        ],
        "interval_note": INTERVAL_NOTE,
        "projection_note": PROJECTION_NOTE,
        "provenance": "SYNTHETIC_DEMO",
    }


def _safe_json(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _constraints(product: dict, rec: dict) -> list[str]:
    notes = []
    pack = int(product.get("pack_size") or 1)
    qty = int(rec.get("suggested_qty") or 0)
    if qty > 0 and pack > 1 and qty % pack != 0:
        notes.append(f"Suggested qty {qty} is not a multiple of pack size {pack}.")
    if qty == 0:
        notes.append("Optimizer selected quantity 0 (budget, pack, or risk trade-off).")
    if not rec.get("expected_arrival_date"):
        notes.append("No expected arrival date stored; projection cannot schedule this receipt.")
    if rec.get("status") == "stale":
        notes.append("Recommendation marked stale after a stock change.")
    return notes


def _deterministic_explanation(product: dict, rec: dict, demand_28: float | None) -> str:
    parts = [
        f"Stock on hand {int(product['stock_on_hand'])} units.",
    ]
    if demand_28 is not None:
        parts.append(f"Forecast demand over 28 days ≈ {demand_28:.1f} units (Demand Interval p50 sum).")
    if product.get("days_of_supply") is not None:
        parts.append(f"Days of supply ≈ {float(product['days_of_supply']):.1f}.")
    so = rec.get("expected_stockout_risk")
    if so is not None:
        parts.append(f"Modeled stockout risk {float(so):.0%}.")
    ex = rec.get("expected_excess_risk")
    if ex is not None:
        parts.append(f"Modeled excess risk {float(ex):.0%}.")
    qty = int(rec.get("suggested_qty") or 0)
    cost = rec.get("estimated_cost_paise")
    if qty > 0:
        cost_txt = f" (~₹{(cost or 0)/100:,.0f})" if cost is not None else ""
        parts.append(f"Optimizer suggested {qty} units{cost_txt}.")
    else:
        parts.append("Optimizer suggested no new purchase.")
    if rec.get("expected_arrival_date"):
        parts.append(f"Predicted arrival {rec['expected_arrival_date']}.")
    return " ".join(parts)


def _build_insights(items: list[dict], products: list[dict], meta: dict) -> list[dict]:
    insights: list[dict] = []
    high_long = [
        row
        for row in items
        if (row.get("stockout_risk") or 0) >= STOCKOUT_HIGH
        and row.get("expected_arrival_date")
        and row.get("suggested_qty", 0) > 0
    ]
    if high_long:
        insights.append(
            {
                "id": "replenishment_attention",
                "title": "Replenishment attention required",
                "severity": "high",
                "text": (
                    f"{len(high_long)} selected SKUs have elevated modeled stockout risk "
                    f"(≥ {STOCKOUT_HIGH:.0%}) with a positive optimizer quantity and a predicted arrival date."
                ),
                "product_ids": [row["product_id"] for row in high_long[:12]],
                "actions": ["view_products", "simulate", "inspect_trace"],
            }
        )

    excessish = [
        p
        for p in products
        if p.get("forecast_28d")
        and float(p["forecast_28d"]) > 0
        and float(p["stock_on_hand"]) > (float(p["forecast_28d"]) / 28.0) * EXCESS_COVER_DAYS
    ]
    if excessish:
        insights.append(
            {
                "id": "excess_cover",
                "title": "Forecast-driven excess cover",
                "severity": "medium",
                "text": (
                    f"{len(excessish)} SKUs hold more than {EXCESS_COVER_DAYS} days of forecast cover "
                    "(value proxy — distinct from Excess Risk Agent probability)."
                ),
                "product_ids": [int(p["product_id"]) for p in excessish[:12]],
                "actions": ["view_excess"],
            }
        )

    if meta.get("as_of_date"):
        insights.append(
            {
                "id": "forecast_origin",
                "title": "Forecast origin",
                "severity": "info",
                "text": (
                    f"Predictive views use forecast as-of {meta['as_of_date']} "
                    f"(model {meta.get('model_version')}). Historical month filters do not rewrite this origin."
                ),
                "product_ids": [],
                "actions": ["data_quality"],
            }
        )
    return insights
