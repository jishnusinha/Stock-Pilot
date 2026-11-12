"""Inventory analytics and reorder calendar routes."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import schemas as S
from app.api.deps import get_db
from app.services import inventory_analytics as ia

router = APIRouter()


def get_filters(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    year: int | None = Query(None),
    month: int | None = Query(None),
    category: str | None = Query(None),
    supplier_id: int | None = Query(None),
    product_id: int | None = Query(None),
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
