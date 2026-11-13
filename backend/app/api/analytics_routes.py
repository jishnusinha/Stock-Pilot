"""Inventory analytics and reorder calendar routes."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import schemas as S
from app.api.deps import get_db
from app.services import inventory_analytics as ia
from app.services import predictive_inventory_analytics as pia

router = APIRouter()


def get_filters(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    year: int | None = Query(None),
    month: int | None = Query(None),
    category: str | None = Query(None),
    supplier_id: int | None = Query(None),
    product_id: int | None = Query(None),
    segment: str | None = Query(None),
) -> ia.Filters:
    try:
        return ia.parse_filters(
            date_from=date_from,
            date_to=date_to,
            year=year,
            month=month,
            category=category,
            supplier_id=supplier_id,
            product_id=product_id,
            segment=segment,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _call(fn, conn: sqlite3.Connection, filters: ia.Filters, **kwargs: Any) -> Any:
    try:
        return fn(conn, filters, **kwargs)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/analytics/overview", response_model=S.AnalyticsResponse)
def analytics_overview(
    filters: ia.Filters = Depends(get_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.overview, conn, filters)


@router.get("/analytics/inventory-trend", response_model=S.AnalyticsResponse)
def analytics_trend(
    filters: ia.Filters = Depends(get_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.inventory_trend, conn, filters)


@router.get("/analytics/turnover", response_model=S.AnalyticsResponse)
def analytics_turnover(
    filters: ia.Filters = Depends(get_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.turnover_series, conn, filters)


@router.get("/analytics/movements", response_model=S.AnalyticsResponse)
def analytics_movements(
    filters: ia.Filters = Depends(get_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.movements, conn, filters)


@router.get("/analytics/top-products", response_model=S.AnalyticsResponse)
def analytics_top(
    filters: ia.Filters = Depends(get_filters),
    limit: int = Query(10, ge=1, le=25),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.top_products, conn, filters, limit=limit)


@router.get("/analytics/inventory-sales", response_model=S.AnalyticsResponse)
def analytics_sales(
    filters: ia.Filters = Depends(get_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.inventory_sales, conn, filters)


@router.get("/analytics/category-breakdown", response_model=S.AnalyticsResponse)
def analytics_categories(
    filters: ia.Filters = Depends(get_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.category_breakdown, conn, filters)


@router.get("/analytics/abc-xyz", response_model=S.AnalyticsResponse)
def analytics_abc(
    filters: ia.Filters = Depends(get_filters),
    cell: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=200),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.abc_xyz, conn, filters, cell=cell, page=page, page_size=page_size)


@router.get("/analytics/slow-moving", response_model=S.AnalyticsResponse)
def analytics_slow(
    filters: ia.Filters = Depends(get_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.slow_moving, conn, filters, page=page, page_size=page_size)


@router.get("/analytics/suppliers", response_model=S.AnalyticsResponse)
def analytics_suppliers(
    filters: ia.Filters = Depends(get_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(ia.suppliers, conn, filters)


@router.get("/analytics/filters", response_model=S.AnalyticsResponse)
def analytics_filters(conn: sqlite3.Connection = Depends(get_db)) -> Any:
    return ia.filter_options(conn)


@router.get("/reorders/calendar", response_model=S.ReorderCalendarResponse)
def reorders_calendar(conn: sqlite3.Connection = Depends(get_db)) -> Any:
    return ia.reorder_calendar(conn)


# ---- StockPilot 3.2 predictive analytics (persisted ML outputs; no training) ----


@router.get("/analytics/predictive/overview", response_model=S.AnalyticsResponse)
def predictive_overview(
    filters: ia.Filters = Depends(get_filters),
    horizon_days: int = Query(28, ge=7, le=28),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    if horizon_days not in (7, 14, 28):
        raise HTTPException(400, "horizon_days must be 7, 14, or 28")
    return _call(pia.overview, conn, filters, horizon_days=horizon_days)


@router.get("/analytics/predictive/demand", response_model=S.AnalyticsResponse)
def predictive_demand(
    filters: ia.Filters = Depends(get_filters),
    horizon_days: int = Query(28, ge=7, le=28),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    if horizon_days not in (7, 14, 28):
        raise HTTPException(400, "horizon_days must be 7, 14, or 28")
    return _call(pia.demand_outlook, conn, filters, horizon_days=horizon_days)


@router.get("/analytics/predictive/inventory-projection", response_model=S.AnalyticsResponse)
def predictive_inventory_projection(
    filters: ia.Filters = Depends(get_filters),
    horizon_days: int = Query(28, ge=7, le=28),
    mode: str = Query("no_reorder"),
    scenario_order_qty: int | None = Query(None, ge=0),
    scenario_lead_days: int | None = Query(None, ge=0, le=28),
    scenario_product_id: int | None = Query(None),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    if horizon_days not in (7, 14, 28):
        raise HTTPException(400, "horizon_days must be 7, 14, or 28")
    if mode not in ("no_reorder", "recommended", "scenario"):
        raise HTTPException(400, "mode must be no_reorder, recommended, or scenario")
    return _call(
        pia.inventory_projection,
        conn,
        filters,
        horizon_days=horizon_days,
        mode=mode,
        scenario_order_qty=scenario_order_qty,
        scenario_lead_days=scenario_lead_days,
        scenario_product_id=scenario_product_id,
    )


@router.get("/analytics/predictive/risks", response_model=S.AnalyticsResponse)
def predictive_risks(
    filters: ia.Filters = Depends(get_filters),
    limit: int = Query(25, ge=1, le=100),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(pia.risks, conn, filters, limit=limit)


@router.get("/analytics/predictive/recommendations", response_model=S.AnalyticsResponse)
def predictive_recommendations(
    filters: ia.Filters = Depends(get_filters),
    limit: int = Query(40, ge=1, le=100),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(pia.recommendations, conn, filters, limit=limit)


@router.get("/analytics/predictive/explain/{product_id}", response_model=S.AnalyticsResponse)
def predictive_explain(
    product_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    try:
        return pia.explain_product(conn, product_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/analytics/predictive/data-quality", response_model=S.AnalyticsResponse)
def predictive_data_quality(
    filters: ia.Filters = Depends(get_filters),
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    return _call(pia.data_quality, conn, filters)
