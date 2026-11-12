"""Inventory analytics over reconstructed daily snapshots and live stock.

Turnover is total period COGS divided by the average of daily total inventory
value. It is never an average of per-SKU turnover ratios. Days inventory
outstanding divides the number of snapshot days by that turnover. It is not
forecast days of supply.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from app.core.config import settings
from app.services.analytics_fingerprint import (
    ALGORITHM_VERSION,
    live_anchor_fingerprint,
    source_fingerprint,
)

PROVENANCE = "SYNTHETIC_RECONSTRUCTED"
TURNOVER_REFERENCE_TARGET = 6.0
ABC_A = 0.80
ABC_B = 0.95
XYZ_X = 0.50
XYZ_Y = 1.00
EXCESS_COVER_DAYS = 45

TURNOVER_DEFINITION = (
    "Period COGS / average daily total closing inventory value. "
    "COGS is fulfilled units times fixed unit cost. "
    "This is not an average of SKU turnover ratios, and monthly figures are not annualized."
)
DIO_DEFINITION = (
    "Snapshot days in the selected window / inventory turnover. "
    "Undefined when turnover is zero. This is not forecast-based days of supply."
)
RATIO_DEFINITION = (
    "Period-end closing inventory value / fulfilled sales revenue in the same window. "
    "Revenue uses each day's selling price on fulfilled units only."
)
COST_MODEL = (
    "Fixed catalog unit_cost_paise. Unfulfilled demand is excluded from units sold, COGS, and revenue."
)
EXCESS_DEFINITION = (
    f"Current on-hand units above {EXCESS_COVER_DAYS} days of forecast demand "
    "(forecast_28d / 28), valued at unit cost. Products without a positive forecast are omitted. "
    "The date filter does not change this current-state proxy."
)
RECONCILIATION_NOTE = (
    "Snapshots are immutable SYNTHETIC_RECONSTRUCTED history. The final snapshot day was reconciled "
    "to stock on hand at generation time. Later operational receipts change live stock only."
)
ABC_RULE = (
    f"ABC uses fulfilled sales revenue, sorted high to low with product id as the tie break. "
    f"A is the head of the list until cumulative revenue reaches {ABC_A:.0%}. "
    f"B is the following band until {ABC_B:.0%}. C is the rest, including zero-revenue SKUs. "
    "The product that crosses a threshold stays in that class."
)
XYZ_RULE = (
    f"XYZ uses the population coefficient of variation of daily demand (sales units, including zeros). "
    f"X is CV < {XYZ_X}, Y is CV < {XYZ_Y}, Z is CV at or above {XYZ_Y} or a zero mean. "
    "This is a statistical segmentation, not a machine-learning model."
)
_CLASS_CACHE: dict[tuple, list[dict]] = {}
_CLASS_LOCK = threading.Lock()

CELL_COPY = {
    "AX": "High revenue contribution and relatively stable demand.",
    "AY": "High revenue contribution and moderately variable demand.",
    "AZ": "High revenue contribution and highly variable or zero-mean demand.",
    "BX": "Mid revenue contribution and relatively stable demand.",
    "BY": "Mid revenue contribution and moderately variable demand.",
    "BZ": "Mid revenue contribution and highly variable or zero-mean demand.",
    "CX": "Low revenue contribution and relatively stable demand.",
    "CY": "Low revenue contribution and moderately variable demand.",
    "CZ": "Low revenue contribution and irregular or zero-mean demand.",
}


@dataclass(frozen=True)
class Filters:
    date_from: str | None = None
    date_to: str | None = None
    year: int | None = None
    month: int | None = None
    category: str | None = None
    supplier_id: int | None = None
    product_id: int | None = None
    segment: str | None = None


def parse_filters(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    year: int | None = None,
    month: int | None = None,
    category: str | None = None,
    supplier_id: int | None = None,
    product_id: int | None = None,
    segment: str | None = None,
) -> Filters:
    start = _date(date_from, "date_from")
    end = _date(date_to, "date_to")
    if start and end and start > end:
        raise ValueError("date_from must be on or before date_to")
    if year is not None and not 1990 <= int(year) <= 2100:
        raise ValueError("year is out of range")
    if month is not None and not 1 <= int(month) <= 12:
        raise ValueError("month must be between 1 and 12")
    cat = (category or "").strip() or None
    if cat is not None and len(cat) > 80:
        raise ValueError("category is too long")
    cell = (segment or "").strip().upper() or None
    if cell is not None and cell not in CELL_COPY:
        raise ValueError("segment must be an ABC–XYZ cell such as AX")
    return Filters(
        date_from=start,
        date_to=end,
        year=int(year) if year is not None else None,
        month=int(month) if month is not None else None,
        category=cat,
        supplier_id=int(supplier_id) if supplier_id is not None else None,
        product_id=int(product_id) if product_id is not None else None,
        segment=cell,
    )


def _date(value: str | None, field: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    return value


def _assert_entities(conn: sqlite3.Connection, filters: Filters) -> None:
    if filters.product_id is not None:
        row = conn.execute(
            "SELECT 1 FROM products WHERE id=? AND is_active=1", (filters.product_id,)
        ).fetchone()
        if not row:
            raise LookupError("Product not found")
    if filters.supplier_id is not None:
        row = conn.execute("SELECT 1 FROM suppliers WHERE id=?", (filters.supplier_id,)).fetchone()
        if not row:
            raise LookupError("Supplier not found")


def _latest_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM analytics_runs
        WHERE status='complete'
        ORDER BY generated_at DESC, id DESC
        LIMIT 1
        """
    ).fetchone()


def _where(
    filters: Filters,
    run_id: int,
    *,
    dates: bool = True,
    conn: sqlite3.Connection | None = None,
    apply_segment: bool = True,
) -> tuple[str, list]:
    clauses = ["s.run_id = ?"]
    params: list = [run_id]
    if dates:
        if filters.date_from:
            clauses.append("s.snapshot_date >= ?")
            params.append(filters.date_from)
        if filters.date_to:
            clauses.append("s.snapshot_date <= ?")
            params.append(filters.date_to)
        if filters.year is not None:
            clauses.append("substr(s.snapshot_date, 1, 4) = ?")
            params.append(f"{filters.year:04d}")
        if filters.month is not None:
            clauses.append("CAST(substr(s.snapshot_date, 6, 2) AS INTEGER) = ?")
            params.append(filters.month)
    if filters.category:
        clauses.append("p.category = ?")
        params.append(filters.category)
    if filters.supplier_id is not None:
        clauses.append("p.supplier_id = ?")
        params.append(filters.supplier_id)
    if filters.product_id is not None:
        clauses.append("s.product_id = ?")
        params.append(filters.product_id)
    if apply_segment and filters.segment:
        if conn is None:
            raise RuntimeError("segment filters require a database connection")
        cohort = _cohort_ids(conn, filters)
        if not cohort:
            clauses.append("0 = 1")
        else:
            marks = ",".join("?" * len(cohort))
            clauses.append(f"s.product_id IN ({marks})")
            params.extend(cohort)
    return " AND ".join(clauses), params


def _product_where(
    filters: Filters,
    *,
    conn: sqlite3.Connection | None = None,
    apply_segment: bool = True,
) -> tuple[str, list]:
    clauses = ["p.is_active = 1"]
    params: list = []
    if filters.category:
        clauses.append("p.category = ?")
        params.append(filters.category)
    if filters.supplier_id is not None:
        clauses.append("p.supplier_id = ?")
        params.append(filters.supplier_id)
    if filters.product_id is not None:
        clauses.append("p.id = ?")
        params.append(filters.product_id)
    if apply_segment and filters.segment:
        if conn is None:
            raise RuntimeError("segment filters require a database connection")
        cohort = _cohort_ids(conn, filters)
        if not cohort:
            clauses.append("0 = 1")
        else:
            marks = ",".join("?" * len(cohort))
            clauses.append(f"p.id IN ({marks})")
            params.extend(cohort)
    return " AND ".join(clauses), params


def _notes(run: sqlite3.Row | None) -> dict:
    if run is None or not run["notes"]:
        return {}
    try:
        parsed = json.loads(run["notes"])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _freshness(conn: sqlite3.Connection, run: sqlite3.Row | None) -> dict:
    if run is None:
        return {
            "freshness": "missing",
            "algorithm_version": ALGORITHM_VERSION,
            "source_fingerprint": None,
            "current_source_fingerprint": None,
            "anchor_fingerprint": None,
            "anchor_drift": None,
            "anchor_note": None,
        }
    current_snapshot = conn.execute("SELECT MAX(sale_date) AS b FROM sales").fetchone()["b"]
    current_fp = source_fingerprint(
        conn, seed=int(run["seed"]), snapshot_date=str(current_snapshot or run["snapshot_date"])
    )
    stored_fp = run["source_fingerprint"] if "source_fingerprint" in run.keys() else None
    stored_anchor = run["anchor_fingerprint"] if "anchor_fingerprint" in run.keys() else None
    live_anchor = live_anchor_fingerprint(conn)
    fresh = (
        run["status"] == "complete"
        and stored_fp == current_fp
        and run["version"] == ALGORITHM_VERSION
        and run["snapshot_date"] == current_snapshot
    )
    drift = bool(stored_anchor and stored_anchor != live_anchor)
    return {
        "freshness": "fresh" if fresh else "stale",
        "algorithm_version": run["version"],
        "source_fingerprint": stored_fp,
        "current_source_fingerprint": current_fp,
        "anchor_fingerprint": stored_anchor,
        "anchor_drift": drift,
        "anchor_note": (
            "Current on-hand stock differs from the frozen reconstruction anchor. Historical snapshots were not rewritten."
            if drift
            else "Current on-hand stock matches the frozen reconstruction anchor."
        ),
    }


def _classified_products(conn: sqlite3.Connection, filters: Filters, run: sqlite3.Row) -> list[dict]:
    """ABC–XYZ classes for the segmentation context. The selected cell is ignored."""
    base = replace(filters, segment=None)
    database_file = conn.execute("PRAGMA database_list").fetchone()["file"]
    cache_key = (
        database_file,
        int(run["id"]),
        base.date_from,
        base.date_to,
        base.year,
        base.month,
        base.category,
        base.supplier_id,
        base.product_id,
    )
    cached = _CLASS_CACHE.get(cache_key)
    if cached is not None:
        return cached
    with _CLASS_LOCK:
        cached = _CLASS_CACHE.get(cache_key)
        if cached is not None:
            return cached
        return _classify_and_store(conn, base, cache_key, int(run["id"]))


def _classify_and_store(
    conn: sqlite3.Connection, base: Filters, cache_key: tuple, run_id: int
) -> list[dict]:
    where, params = _where(base, run_id, conn=conn, apply_segment=False)
    raw = conn.execute(
        f"""
        WITH filt AS (
          SELECT s.*, p.sku, p.name, p.category
          FROM inventory_daily_snapshots s
          JOIN products p ON p.id = s.product_id
          WHERE {where}
        ),
        ends AS (
          SELECT product_id, MAX(snapshot_date) AS snapshot_date FROM filt GROUP BY product_id
        )
        SELECT f.product_id AS product_id, p.sku AS sku, p.name AS name, p.category AS category,
               AVG(f.demand_units) AS mean_demand,
               AVG(f.demand_units * f.demand_units) AS mean_square,
               SUM(f.revenue_paise) AS revenue_paise,
               e.closing_value_paise AS inventory_value_paise
        FROM filt f
        JOIN products p ON p.id = f.product_id
        JOIN ends ON ends.product_id = f.product_id
        JOIN filt e ON e.product_id = ends.product_id AND e.snapshot_date = ends.snapshot_date
        GROUP BY f.product_id
        """,
        params,
    ).fetchall()
    products = []
    for row in raw:
        xyz, cv = _classify_xyz(float(row["mean_demand"] or 0), float(row["mean_square"] or 0))
        products.append(
            {
                "product_id": int(row["product_id"]),
                "sku": row["sku"],
                "name": row["name"],
                "category": row["category"],
                "revenue_paise": int(row["revenue_paise"] or 0),
                "inventory_value_paise": int(row["inventory_value_paise"] or 0),
                "xyz": xyz,
                "cv": cv,
            }
        )
    _classify_abc(products)
    for row in products:
        row["cell"] = f"{row['abc']}{row['xyz']}"
        row["interpretation"] = CELL_COPY[row["cell"]]
    _CLASS_CACHE[cache_key] = products
    if len(_CLASS_CACHE) > 24:
        _CLASS_CACHE.pop(next(iter(_CLASS_CACHE)))
    return products


def _cohort_ids(conn: sqlite3.Connection, filters: Filters) -> list[int]:
    run = _latest_run(conn)
    if run is None or not filters.segment:
        return []
    return [int(row["product_id"]) for row in _classified_products(conn, filters, run) if row["cell"] == filters.segment]


def _run_meta(run: sqlite3.Row | None, *, ready: bool, conn: sqlite3.Connection | None = None) -> dict:
    if run is None:
        return {
            "ready": False,
            "run_id": None,
            "seed": None,
            "snapshot_date": None,
            "generated_at": None,
            "provenance": PROVENANCE,
            "freshness": "missing",
            "note": "Analytics history has not been generated. Run: python -m app.cli build-analytics --seed 42",
        }
    body = {
        "ready": ready,
        "run_id": int(run["id"]),
        "seed": int(run["seed"]),
        "snapshot_date": run["snapshot_date"],
        "generated_at": run["generated_at"],
        "provenance": PROVENANCE,
        "algorithm_version": run["version"],
        "source_fingerprint": run["source_fingerprint"] if "source_fingerprint" in run.keys() else None,
        "anchor_fingerprint": run["anchor_fingerprint"] if "anchor_fingerprint" in run.keys() else None,
        "note": None,
    }
    if conn is not None:
        body.update(_freshness(conn, run))
    return body


def _daily(conn: sqlite3.Connection, filters: Filters) -> tuple[sqlite3.Row | None, list[dict]]:
    _assert_entities(conn, filters)
    run = _latest_run(conn)
    if run is None:
        return None, []
    where, params = _where(filters, int(run["id"]), conn=conn)
    rows = conn.execute(
        f"""
        SELECT s.snapshot_date AS snapshot_date,
               SUM(s.closing_value_paise) AS closing_value,
               SUM(s.closing_stock) AS closing_units,
               SUM(s.opening_stock) AS opening_units,
               SUM(s.opening_stock * s.unit_cost_paise) AS opening_value,
               SUM(s.received_units) AS receipts_units,
               SUM(s.received_units * s.unit_cost_paise) AS receipts_value,
               SUM(s.sold_units) AS sold_units,
               SUM(s.cogs_paise) AS cogs,
               SUM(s.revenue_paise) AS revenue,
               SUM(s.returned_units) AS returns_units,
               SUM(s.returned_units * s.unit_cost_paise) AS returns_value,
               SUM(s.adjustment_units) AS adjustment_units,
               SUM(s.adjustment_units * s.unit_cost_paise) AS adjustment_value,
               SUM(s.writeoff_units) AS writeoff_units,
               SUM(s.writeoff_units * s.unit_cost_paise) AS writeoff_value
        FROM inventory_daily_snapshots s
        JOIN products p ON p.id = s.product_id
        WHERE {where}
        GROUP BY s.snapshot_date
        ORDER BY s.snapshot_date
        """,
        params,
    ).fetchall()
    return run, [dict(r) for r in rows]


def _live(conn: sqlite3.Connection, filters: Filters) -> tuple[int, int]:
    where, params = _product_where(filters, conn=conn)
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(p.stock_on_hand), 0) AS units,
               COALESCE(SUM(p.stock_on_hand * p.unit_cost_paise), 0) AS value
        FROM products p
        WHERE {where}
        """,
        params,
    ).fetchone()
    return int(row["units"]), int(row["value"])


def _excess(conn: sqlite3.Connection, filters: Filters) -> int | None:
    where, params = _product_where(filters, conn=conn)
    rows = conn.execute(
        f"""
        SELECT p.stock_on_hand, p.unit_cost_paise, r.forecast_28d
        FROM products p
        LEFT JOIN product_risk_cache r ON r.product_id = p.id
        WHERE {where}
        """,
        params,
    ).fetchall()
    total = 0
    any_forecast = False
    for row in rows:
        forecast = row["forecast_28d"]
        if forecast is None or float(forecast) <= 0:
            continue
        any_forecast = True
        excess_units = float(row["stock_on_hand"]) - (float(forecast) / 28.0) * EXCESS_COVER_DAYS
        if excess_units > 0:
            total += int(round(excess_units * int(row["unit_cost_paise"])))
    if not any_forecast:
        return None
    return total


def _months(days: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for day in days:
        buckets.setdefault(str(day["snapshot_date"])[:7], []).append(day)
    out = []
    previous_value: int | None = None
    for month in sorted(buckets):
        chunk = buckets[month]
        closing_value = int(chunk[-1]["closing_value"] or 0)
        revenue = int(sum(int(d["revenue"] or 0) for d in chunk))
        cogs = int(sum(int(d["cogs"] or 0) for d in chunk))
        avg_value = sum(int(d["closing_value"] or 0) for d in chunk) / len(chunk)
        turnover = (cogs / avg_value) if avg_value > 0 else None
        ratio = (closing_value / revenue) if revenue > 0 else None
        abs_change = None if previous_value is None else closing_value - previous_value
        pct_change = None
        if previous_value not in (None, 0) and abs_change is not None:
            pct_change = (abs_change / previous_value) * 100.0
        out.append(
            {
                "month": month,
                "inventory_value_paise": closing_value,
                "stock_units": int(chunk[-1]["closing_units"] or 0),
                "revenue_paise": revenue,
                "cogs_paise": cogs,
                "average_inventory_value_paise": avg_value,
                "turnover": turnover,
                "inventory_to_sales": ratio,
                "days": len(chunk),
                "absolute_change_paise": abs_change,
                "percent_change": pct_change,
                "previous_inventory_value_paise": previous_value,
            }
        )
        previous_value = closing_value
    return out


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _blank_metrics() -> dict:
    return {
        "period_start": None,
        "period_end": None,
        "period_days": 0,
        "inventory_value_paise": None,
        "inventory_value_basis": "period_end_closing_cost",
        "stock_units": None,
        "turnover": None,
        "days_inventory_outstanding": None,
        "inventory_to_sales": None,
        "cogs_paise": None,
        "revenue_paise": None,
        "average_inventory_value_paise": None,
        "live_matches_period_end": None,
    }


def overview(conn: sqlite3.Connection, filters: Filters) -> dict:
    run, days = _daily(conn, filters)
    live_units, live_value = _live(conn, filters)
    meta = _run_meta(run, ready=run is not None, conn=conn)
    body = {
        **meta,
        **_blank_metrics(),
        "live_inventory_value_paise": live_value,
        "live_stock_units": live_units,
        "historical_label": "Historical as-of-period",
        "current_label": "Current operational state",
        "stock_units_meaning": "period_end_historical_closing_stock",
        "live_stock_meaning": "current_operational_stock",
        "excess_meaning": "current_operational_overlay",
        "segment": filters.segment,
        "turnover_definition": TURNOVER_DEFINITION,
        "turnover_reference_target": TURNOVER_REFERENCE_TARGET,
        "dio_definition": DIO_DEFINITION,
        "inventory_to_sales_definition": RATIO_DEFINITION,
        "cost_model": COST_MODEL,
        "excess_inventory_value_paise": _excess(conn, filters),
        "excess_definition": EXCESS_DEFINITION,
        "reconciliation_note": RECONCILIATION_NOTE if run is not None else None,
        "insights": [],
    }
    if run is None or not days:
        return body
    cogs = int(sum(int(d["cogs"] or 0) for d in days))
    revenue = int(sum(int(d["revenue"] or 0) for d in days))
    avg_value = sum(int(d["closing_value"] or 0) for d in days) / len(days)
    end_value = int(days[-1]["closing_value"] or 0)
    end_units = int(days[-1]["closing_units"] or 0)
    turnover = _ratio(cogs, avg_value)
    dio = None if turnover in (None, 0) else len(days) / turnover
    body.update(
        {
            "period_start": days[0]["snapshot_date"],
            "period_end": days[-1]["snapshot_date"],
            "period_days": len(days),
            "inventory_value_paise": end_value,
            "stock_units": end_units,
            "turnover": turnover,
            "days_inventory_outstanding": dio,
            "inventory_to_sales": _ratio(end_value, revenue),
            "cogs_paise": cogs,
            "revenue_paise": revenue,
            "average_inventory_value_paise": avg_value,
            "live_matches_period_end": days[-1]["snapshot_date"] == run["snapshot_date"] and live_units == end_units,
        }
    )
    body["insights"] = _insights(conn, filters, run, days, _months(days))
    body["reconciliation"] = _reconciliation_facts(
        conn, filters, run, str(days[0]["snapshot_date"]), str(days[-1]["snapshot_date"])
    )
    return body


def inventory_trend(conn: sqlite3.Connection, filters: Filters) -> dict:
    run, days = _daily(conn, filters)
    return {**_run_meta(run, ready=run is not None, conn=conn), "months": _months(days), "cost_model": COST_MODEL}


def turnover_series(conn: sqlite3.Connection, filters: Filters) -> dict:
    run, days = _daily(conn, filters)
    months = [
        {
            "month": m["month"],
            "turnover": m["turnover"],
            "cogs_paise": m["cogs_paise"],
            "average_inventory_value_paise": m["average_inventory_value_paise"],
            "days": m["days"],
        }
        for m in _months(days)
    ]
    return {
        **_run_meta(run, ready=run is not None, conn=conn),
        "months": months,
        "definition": TURNOVER_DEFINITION,
        "reference_target": TURNOVER_REFERENCE_TARGET,
    }


def movements(conn: sqlite3.Connection, filters: Filters) -> dict:
    run, days = _daily(conn, filters)
    body = {
        **_run_meta(run, ready=run is not None, conn=conn),
        "formula": "closing = opening + receipts + returns + adjustments - fulfilled sales - write-offs",
        "conserved_units": None,
        "conserved_value": None,
        "opening_units": None,
        "receipts_units": None,
        "fulfilled_sales_units": None,
        "returns_units": None,
        "adjustments_units": None,
        "writeoff_units": None,
        "closing_units": None,
        "opening_value_paise": None,
        "receipts_value_paise": None,
        "cogs_paise": None,
        "returns_value_paise": None,
        "adjustments_value_paise": None,
        "writeoff_value_paise": None,
        "closing_value_paise": None,
    }
    if not days:
        return body
    opening_units = int(days[0]["opening_units"] or 0)
    receipts_units = int(sum(int(d["receipts_units"] or 0) for d in days))
    sold_units = int(sum(int(d["sold_units"] or 0) for d in days))
    returns_units = int(sum(int(d["returns_units"] or 0) for d in days))
    adjustment_units = int(sum(int(d["adjustment_units"] or 0) for d in days))
    writeoff_units = int(sum(int(d["writeoff_units"] or 0) for d in days))
    closing_units = int(days[-1]["closing_units"] or 0)
    opening_value = int(days[0]["opening_value"] or 0)
    receipts_value = int(sum(int(d["receipts_value"] or 0) for d in days))
    cogs = int(sum(int(d["cogs"] or 0) for d in days))
    returns_value = int(sum(int(d["returns_value"] or 0) for d in days))
    adjustment_value = int(sum(int(d["adjustment_value"] or 0) for d in days))
    writeoff_value = int(sum(int(d["writeoff_value"] or 0) for d in days))
    closing_value = int(days[-1]["closing_value"] or 0)
    expected_units = opening_units + receipts_units + returns_units + adjustment_units - sold_units - writeoff_units
    expected_value = opening_value + receipts_value + returns_value + adjustment_value - cogs - writeoff_value
    body.update(
        {
            "conserved_units": expected_units == closing_units,
            "conserved_value": expected_value == closing_value,
            "opening_units": opening_units,
            "receipts_units": receipts_units,
            "fulfilled_sales_units": sold_units,
            "returns_units": returns_units,
            "adjustments_units": adjustment_units,
            "writeoff_units": writeoff_units,
            "closing_units": closing_units,
            "opening_value_paise": opening_value,
            "receipts_value_paise": receipts_value,
            "cogs_paise": cogs,
            "returns_value_paise": returns_value,
            "adjustments_value_paise": adjustment_value,
            "writeoff_value_paise": writeoff_value,
            "closing_value_paise": closing_value,
        }
    )
    facts = _reconciliation_facts(conn, filters, run, str(days[0]["snapshot_date"]), str(days[-1]["snapshot_date"]))
    routine_receipts = receipts_units - int(facts["up_units"])
    routine_receipts_value = receipts_value - int(facts["up_value_paise"])
    routine_writeoffs = writeoff_units - int(facts["down_units"])
    routine_writeoff_value = writeoff_value - int(facts["down_value_paise"])
    split_units = (
        opening_units
        + routine_receipts
        + int(facts["up_units"])
        + returns_units
        + adjustment_units
        - sold_units
        - routine_writeoffs
        - int(facts["down_units"])
    )
    body.update(
        {
            "routine_receipts_units": routine_receipts,
            "reconciliation_receipt_units": int(facts["up_units"]),
            "routine_receipts_value_paise": routine_receipts_value,
            "reconciliation_receipt_value_paise": int(facts["up_value_paise"]),
            "routine_writeoff_units": routine_writeoffs,
            "reconciliation_writeoff_units": int(facts["down_units"]),
            "routine_writeoff_value_paise": routine_writeoff_value,
            "reconciliation_writeoff_value_paise": int(facts["down_value_paise"]),
            "reconciliation_split_conserved": split_units == closing_units,
            "reconciliation": facts,
        }
    )
    return body


def _reconciliation_facts(
    conn: sqlite3.Connection,
    filters: Filters,
    run: sqlite3.Row,
    start: str,
    end: str,
) -> dict:
    """Terminal adjustments inside the selected window, kept separate from routine simulation."""
    where, params = _where(filters, int(run["id"]), conn=conn, dates=False)
    row = conn.execute(
        f"""
        SELECT
          COALESCE(SUM(CASE WHEN l.event_type = 'receipt' THEN l.quantity_change ELSE 0 END), 0) AS up_units,
          COALESCE(SUM(CASE WHEN l.event_type = 'receipt' THEN l.quantity_change * l.unit_cost_paise ELSE 0 END), 0) AS up_value,
          COALESCE(SUM(CASE WHEN l.event_type = 'writeoff' THEN -l.quantity_change ELSE 0 END), 0) AS down_units,
          COALESCE(SUM(CASE WHEN l.event_type = 'writeoff' THEN -l.quantity_change * l.unit_cost_paise ELSE 0 END), 0) AS down_value,
          COUNT(DISTINCT CASE WHEN l.event_type = 'receipt' AND l.quantity_change > 0 THEN l.product_id END) AS products_up,
          COUNT(DISTINCT CASE WHEN l.event_type = 'writeoff' AND l.quantity_change < 0 THEN l.product_id END) AS products_down
        FROM inventory_ledger l
        JOIN products p ON p.id = l.product_id
        JOIN inventory_daily_snapshots s
          ON s.run_id = l.run_id AND s.product_id = l.product_id AND s.snapshot_date = date(l.event_at)
        WHERE l.reference = 'RECONCILE_TO_SNAPSHOT'
          AND date(l.event_at) >= ?
          AND date(l.event_at) <= ?
          AND {where}
        """,
        [start, end, *params],
    ).fetchone()
    in_window = start <= str(run["snapshot_date"]) <= end
    matched = 0
    if in_window:
        matched = int(
            conn.execute(
                f"""
                SELECT COUNT(DISTINCT s.product_id)
                FROM inventory_daily_snapshots s
                JOIN products p ON p.id = s.product_id
                WHERE {where}
                  AND s.snapshot_date = ?
                  AND s.product_id NOT IN (
                    SELECT l.product_id
                    FROM inventory_ledger l
                    WHERE l.run_id = s.run_id
                      AND l.reference = 'RECONCILE_TO_SNAPSHOT'
                      AND date(l.event_at) = s.snapshot_date
                  )
                """,
                [*params, run["snapshot_date"]],
            ).fetchone()[0]
        )
    up_units = int(row["up_units"] or 0)
    down_units = int(row["down_units"] or 0)
    up_value = int(row["up_value"] or 0)
    down_value = int(row["down_value"] or 0)
    return {
        "products_up": int(row["products_up"] or 0),
        "products_down": int(row["products_down"] or 0),
        "products_matched": matched,
        "up_units": up_units,
        "down_units": down_units,
        "up_value_paise": up_value,
        "down_value_paise": down_value,
        "net_units": up_units - down_units,
        "absolute_units": up_units + down_units,
        "net_value_paise": up_value - down_value,
        "absolute_value_paise": up_value + down_value,
        "reconciliation_date": run["snapshot_date"],
        "in_selected_window": in_window,
        "provenance": PROVENANCE,
        "source": "SYNTHETIC_RECONSTRUCTED terminal anchor adjustment",
        "explanation": (
            "Reconstruction walks forward from recorded demand and simulated replenishment. "
            "On the final snapshot day the closing balance is aligned to the stock anchor frozen at generation time. "
            "That alignment is a reconciliation receipt or write-off. It is not a supplier delivery and it is not observed purchasing. "
            "Excluding it would leave the displayed series short of the recorded closing inventory."
            if in_window
            else "The terminal reconciliation date is outside this window, so reconciliation totals are zero here. "
            "Movements inside the window still conserve to that window's closing snapshot."
        ),
    }


def inventory_sales(conn: sqlite3.Connection, filters: Filters) -> dict:
    run, days = _daily(conn, filters)
    months = [
        {
            "month": m["month"],
            "inventory_value_paise": m["inventory_value_paise"],
            "revenue_paise": m["revenue_paise"],
            "inventory_to_sales": m["inventory_to_sales"],
        }
        for m in _months(days)
    ]
    return {**_run_meta(run, ready=run is not None, conn=conn), "months": months, "definition": RATIO_DEFINITION}


def _ranked_products(conn: sqlite3.Connection, filters: Filters, run_id: int) -> list[dict]:
    where, params = _where(filters, run_id, conn=conn)
    rows = conn.execute(
        f"""
        WITH filt AS (
          SELECT s.*
          FROM inventory_daily_snapshots s
          JOIN products p ON p.id = s.product_id
          WHERE {where}
        ),
        ends AS (
          SELECT product_id, MAX(snapshot_date) AS snapshot_date
          FROM filt
          GROUP BY product_id
        )
        SELECT p.id AS product_id, p.sku, p.name, p.category,
               e.closing_stock AS stock_units,
               e.closing_value_paise AS inventory_value_paise,
               COALESCE(t.sold_units, 0) AS sold_units,
               COALESCE(t.revenue_paise, 0) AS revenue_paise
        FROM ends
        JOIN filt e ON e.product_id = ends.product_id AND e.snapshot_date = ends.snapshot_date
        JOIN products p ON p.id = ends.product_id
        LEFT JOIN (
          SELECT product_id, SUM(sold_units) AS sold_units, SUM(revenue_paise) AS revenue_paise
          FROM filt
          GROUP BY product_id
        ) t ON t.product_id = ends.product_id
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def _top(rows: list[dict], key: str, limit: int) -> list[dict]:
    ordered = sorted(rows, key=lambda r: (-int(r[key] or 0), int(r["product_id"])))
    out = []
    for index, row in enumerate(ordered[:limit], start=1):
        out.append(
            {
                "rank": index,
                "product_id": int(row["product_id"]),
                "sku": row["sku"],
                "name": row["name"],
                "category": row["category"],
                "inventory_value_paise": int(row["inventory_value_paise"] or 0),
                "stock_units": int(row["stock_units"] or 0),
                "revenue_paise": int(row["revenue_paise"] or 0),
                "sold_units": int(row["sold_units"] or 0),
            }
        )
    return out


def top_products(conn: sqlite3.Connection, filters: Filters, *, limit: int = 10) -> dict:
    if limit < 1 or limit > 25:
        raise ValueError("limit must be between 1 and 25")
    run, _days = _daily(conn, filters)
    rows = _ranked_products(conn, filters, int(run["id"])) if run is not None else []
    return {
        **_run_meta(run, ready=run is not None, conn=conn),
        "limit": limit,
        "by_value": _top(rows, "inventory_value_paise", limit),
        "by_quantity": _top(rows, "stock_units", limit),
        "by_revenue": _top(rows, "revenue_paise", limit),
        "by_volume": _top(rows, "sold_units", limit),
    }


def category_breakdown(conn: sqlite3.Connection, filters: Filters) -> dict:
    run, _days = _daily(conn, filters)
    if run is None:
        return {**_run_meta(run, ready=False, conn=conn), "categories": []}
    grouped: dict[str, dict[str, int]] = {}
    for row in _ranked_products(conn, filters, int(run["id"])):
        bucket = grouped.setdefault(
            str(row["category"]),
            {"sku_count": 0, "inventory_value_paise": 0, "stock_units": 0, "revenue_paise": 0},
        )
        bucket["sku_count"] += 1
        bucket["inventory_value_paise"] += int(row["inventory_value_paise"] or 0)
        bucket["stock_units"] += int(row["stock_units"] or 0)
        bucket["revenue_paise"] += int(row["revenue_paise"] or 0)
    total_value = sum(item["inventory_value_paise"] for item in grouped.values())
    categories = []
    for name, bucket in sorted(grouped.items(), key=lambda item: (-item[1]["inventory_value_paise"], item[0])):
        value = bucket["inventory_value_paise"]
        categories.append(
            {
                "category": name,
                **bucket,
                "value_share": (value / total_value) if total_value else None,
            }
        )
    return {**_run_meta(run, ready=True, conn=conn), "categories": categories}


def _classify_xyz(mean_demand: float, mean_square: float) -> tuple[str, float | None]:
    if mean_demand <= 1e-9:
        return "Z", None
    variance = max(0.0, mean_square - mean_demand * mean_demand)
    cv = math.sqrt(variance) / mean_demand
    if cv < XYZ_X:
        return "X", cv
    if cv < XYZ_Y:
        return "Y", cv
    return "Z", cv


def _classify_abc(rows: list[dict]) -> None:
    ordered = sorted(rows, key=lambda r: (-int(r["revenue_paise"]), int(r["product_id"])))
    total = sum(int(r["revenue_paise"]) for r in ordered)
    previous = 0.0
    for row in ordered:
        if total <= 0:
            row["abc"] = "C"
            continue
        share_before = previous / total
        previous += int(row["revenue_paise"])
        if share_before < ABC_A:
            row["abc"] = "A"
        elif share_before < ABC_B:
            row["abc"] = "B"
        else:
            row["abc"] = "C"


def abc_xyz(
    conn: sqlite3.Connection,
    filters: Filters,
    *,
    cell: str | None = None,
    page: int = 1,
    page_size: int = 200,
) -> dict:
    if page < 1 or page_size < 1 or page_size > 200:
        raise ValueError("page must be >= 1 and page_size must be between 1 and 200")
    if cell is not None and cell not in CELL_COPY:
        raise ValueError("cell must be a class such as AX")
    base_filters = replace(filters, segment=None)
    run, _days = _daily(conn, base_filters)
    base = {
        **_run_meta(run, ready=run is not None, conn=conn),
        "abc_rule": ABC_RULE,
        "xyz_rule": XYZ_RULE,
        "revenue_metric": "fulfilled_sales_revenue",
        "variability_metric": "population_cv_of_daily_demand",
        "segmentation_note": (
            "Class boundaries use the selected period and the category, supplier, and product filters. "
            "A selected cell filters the other analytics to that cohort and does not redraw these boundaries."
        ),
        "cells": [],
        "products": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }
    if run is None:
        return base
    products = _classified_products(conn, base_filters, run)
    total_value = sum(int(r["inventory_value_paise"]) for r in products) or 0
    cells = []
    for abc in "ABC":
        for xyz in "XYZ":
            key = f"{abc}{xyz}"
            members = [r for r in products if r["cell"] == key]
            value = sum(int(r["inventory_value_paise"]) for r in members)
            revenue = sum(int(r["revenue_paise"]) for r in members)
            cells.append(
                {
                    "cell": key,
                    "abc": abc,
                    "xyz": xyz,
                    "sku_count": len(members),
                    "inventory_value_paise": value,
                    "revenue_paise": revenue,
                    "value_share": (value / total_value) if total_value else None,
                    "interpretation": CELL_COPY[key],
                }
            )
    visible = [r for r in products if cell is None or r["cell"] == cell]
    visible.sort(key=lambda r: (r["cell"], -r["inventory_value_paise"], r["product_id"]))
    start = (page - 1) * page_size
    base.update({"cells": cells, "products": visible[start : start + page_size], "total": len(visible)})
    return base


def slow_moving(
    conn: sqlite3.Connection,
    filters: Filters,
    *,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    if page < 1 or page_size < 1 or page_size > 200:
        raise ValueError("page must be >= 1 and page_size must be between 1 and 200")
    run, days = _daily(conn, filters)
    definition = (
        "Fulfilled sales and days since recorded demand are historical, ending on the selected period. "
        "historical_stock_units is that period's closing snapshot. "
        "current_stock_units, forecast cover, risk, and the excess proxy describe the current operational state. "
        "They were not known during the historical month. No expiry dates are shown."
    )
    body = {
        **_run_meta(run, ready=run is not None, conn=conn),
        "definition": definition,
        "as_of": days[-1]["snapshot_date"] if days else None,
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }
    if run is None or not days:
        return body
    as_of = datetime.strptime(str(days[-1]["snapshot_date"]), "%Y-%m-%d")
    start_30 = (as_of - timedelta(days=29)).date().isoformat()
    start_90 = (as_of - timedelta(days=89)).date().isoformat()
    as_of_s = as_of.date().isoformat()
    where, params = _where(filters, int(run["id"]), conn=conn)
    id_rows = conn.execute(
        f"""
        SELECT DISTINCT s.product_id
        FROM inventory_daily_snapshots s
        JOIN products p ON p.id = s.product_id
        WHERE {where}
        """,
        params,
    ).fetchall()
    ids = [int(r["product_id"]) for r in id_rows]
    if not ids:
        return body
    marks = ",".join("?" * len(ids))

    def window_map(start: str) -> dict[int, int]:
        rows = conn.execute(
            f"""
            SELECT product_id, COALESCE(SUM(sold_units), 0) AS units
            FROM inventory_daily_snapshots
            WHERE run_id=? AND snapshot_date>=? AND snapshot_date<=? AND product_id IN ({marks})
            GROUP BY product_id
            """,
            [int(run["id"]), start, as_of_s, *ids],
        ).fetchall()
        return {int(r["product_id"]): int(r["units"]) for r in rows}

    sold90 = window_map(start_90)
    sold30 = window_map(start_30)
    hist_rows = conn.execute(
        f"""
        SELECT s.product_id AS product_id, s.closing_stock AS closing_stock, s.closing_value_paise AS closing_value
        FROM inventory_daily_snapshots s
        JOIN (
          SELECT product_id, MAX(snapshot_date) AS snapshot_date
          FROM inventory_daily_snapshots
          WHERE run_id=? AND snapshot_date<=? AND product_id IN ({marks})
          GROUP BY product_id
        ) e ON e.product_id = s.product_id AND e.snapshot_date = s.snapshot_date
        WHERE s.run_id=?
        """,
        [int(run["id"]), as_of_s, *ids, int(run["id"])],
    ).fetchall()
    historical = {int(r["product_id"]): (int(r["closing_stock"]), int(r["closing_value"])) for r in hist_rows}
    last_sale_rows = conn.execute(
        f"""
        SELECT product_id, MAX(snapshot_date) AS sale_date
        FROM inventory_daily_snapshots
        WHERE run_id=? AND demand_units > 0 AND snapshot_date<=? AND product_id IN ({marks})
        GROUP BY product_id
        """,
        [int(run["id"]), as_of_s, *ids],
    ).fetchall()
    last_sale = {int(r["product_id"]): r["sale_date"] for r in last_sale_rows}
    info_rows = conn.execute(
        f"""
        SELECT p.id, p.sku, p.name, p.category, p.stock_on_hand, p.unit_cost_paise,
               r.risk_level, r.days_of_supply, r.forecast_28d
        FROM products p
        LEFT JOIN product_risk_cache r ON r.product_id = p.id
        WHERE p.id IN ({marks})
        """,
        ids,
    ).fetchall()
    items = []
    for row in info_rows:
        pid = int(row["id"])
        stock = int(row["stock_on_hand"])
        cost = int(row["unit_cost_paise"])
        forecast = row["forecast_28d"]
        forecast_daily = (float(forecast) / 28.0) if forecast is not None and float(forecast) > 0 else None
        excess_units = None if forecast_daily is None else max(0.0, stock - forecast_daily * EXCESS_COVER_DAYS)
        sale_on = last_sale.get(pid)
        days_since = None if sale_on is None else (as_of.date() - datetime.strptime(sale_on, "%Y-%m-%d").date()).days
        cover = None if row["days_of_supply"] is None else float(row["days_of_supply"])
        s90 = sold90.get(pid, 0)
        reasons = []
        if s90 == 0 and stock > 0:
            reasons.append("no_fulfilled_sales_90")
        if excess_units is not None and excess_units > 0:
            reasons.append("excess_proxy")
        if days_since is None and stock > 0:
            reasons.append("no_recorded_demand")
        elif days_since is not None and days_since >= 60:
            reasons.append("stale_demand")
        if cover is not None and cover > 90:
            reasons.append("high_forecast_cover")
        if not reasons:
            continue
        action, basis = _slow_action(reasons)
        hist_units, hist_value = historical.get(pid, (None, None))
        items.append(
            {
                "product_id": pid,
                "sku": row["sku"],
                "name": row["name"],
                "category": row["category"],
                "stock_units": stock,
                "inventory_value_paise": stock * cost,
                "historical_stock_units": hist_units,
                "historical_inventory_value_paise": hist_value,
                "current_stock_units": stock,
                "current_inventory_value_paise": stock * cost,
                "sales_time_basis": "historical_window",
                "stock_time_basis": "current_operational_stock",
                "forecast_time_basis": "current_operational_overlay",
                "sold_units_30d": sold30.get(pid, 0),
                "sold_units_90d": s90,
                "forecast_daily_demand": forecast_daily,
                "forecast_days_of_supply": cover,
                "days_since_recorded_sale": days_since,
                "excess_units": None if excess_units is None else round(excess_units, 2),
                "excess_value_paise": None if excess_units is None else int(round(excess_units * cost)),
                "risk_level": row["risk_level"],
                "suggested_action": action,
                "action_basis": basis,
            }
        )
    items.sort(key=lambda r: (-(r["excess_value_paise"] or 0), -r["inventory_value_paise"], r["product_id"]))
    start = (page - 1) * page_size
    body["total"] = len(items)
    body["items"] = items[start : start + page_size]
    return body


def _slow_action(reasons: list[str]) -> tuple[str, str]:
    if "no_fulfilled_sales_90" in reasons or "no_recorded_demand" in reasons:
        return (
            "No fulfilled sales in the last 90 days. Review a purchasing hold, transfer, or markdown.",
            "no_sales_90",
        )
    if "excess_proxy" in reasons:
        return (
            "On-hand stock is above 45 days of forecast demand. Reduce the next replenishment.",
            "excess_proxy",
        )
    if "stale_demand" in reasons:
        return (
            "No recorded demand for 60 days or more. Confirm the SKU should stay active.",
            "stale_demand",
        )
    return (
        "Forecast days of supply exceed 90. That cover measure is not accounting days inventory outstanding.",
        "high_forecast_cover",
    )


def suppliers(conn: sqlite3.Connection, filters: Filters) -> dict:
    _assert_entities(conn, filters)
    run = _latest_run(conn)
    where, params = _product_where(filters, conn=conn)
    rows = conn.execute(
        f"""
        SELECT s.id AS supplier_id, s.name, s.base_lead_days, s.delivery_reliability,
               COUNT(p.id) AS product_count,
               COALESCE(SUM(p.stock_on_hand), 0) AS stock_units,
               COALESCE(SUM(p.stock_on_hand * p.unit_cost_paise), 0) AS stock_value_paise
        FROM suppliers s
        LEFT JOIN products p ON p.supplier_id = s.id AND {where}
        GROUP BY s.id
        ORDER BY stock_value_paise DESC, s.name ASC
        """,
        params,
    ).fetchall()
    receipt_map: dict[int, sqlite3.Row] = {}
    open_map: dict[int, int] = {}
    if run is not None:
        for rec in conn.execute(
            f"""
            SELECT r.supplier_id AS supplier_id, COUNT(*) AS n,
                   AVG(r.delay_days) AS avg_delay, AVG(r.on_time) AS on_time
            FROM inventory_receipts r
            JOIN products p ON p.id = r.product_id
            WHERE r.run_id=? AND r.kind='replenishment' AND {where}
            GROUP BY r.supplier_id
            """,
            [int(run["id"]), *params],
        ):
            receipt_map[int(rec["supplier_id"])] = rec
    for rec in conn.execute(
        f"""
        SELECT p.supplier_id AS supplier_id, COALESCE(SUM(o.qty), 0) AS qty
        FROM reorders o
        JOIN products p ON p.id = o.product_id
        WHERE o.status IN ('pending', 'approved') AND {where}
        GROUP BY p.supplier_id
        """,
        params,
    ):
        open_map[int(rec["supplier_id"])] = int(rec["qty"])
    items = []
    for row in rows:
        if filters.supplier_id is not None and int(row["supplier_id"]) != filters.supplier_id:
            continue
        if filters.category or filters.product_id or filters.supplier_id or filters.segment:
            if int(row["product_count"] or 0) == 0 and filters.supplier_id is None:
                continue
        rec = receipt_map.get(int(row["supplier_id"]))
        n_receipts = int(rec["n"]) if rec is not None else 0
        items.append(
            {
                "supplier_id": int(row["supplier_id"]),
                "name": row["name"],
                "product_count": int(row["product_count"] or 0),
                "stock_units": int(row["stock_units"] or 0),
                "stock_value_paise": int(row["stock_value_paise"] or 0),
                "modeled_lead_days": int(row["base_lead_days"]),
                "catalog_reliability": float(row["delivery_reliability"]),
                "simulated_receipts": n_receipts,
                "simulated_on_time_rate": float(rec["on_time"]) if rec is not None and n_receipts else None,
                "average_delay_days": float(rec["avg_delay"]) if rec is not None and n_receipts else None,
                "open_reorder_qty": open_map.get(int(row["supplier_id"]), 0),
            }
        )
    return {
        **_run_meta(run, ready=run is not None, conn=conn),
        "catalog_reliability_label": (
            "catalog_reliability is the synthetic supplier parameter used when the catalog was generated. "
            "It is not a measured on-time rate."
        ),
        "simulated_label": (
            "simulated_on_time_rate counts reconstructed replenishment receipts whose drawn delay was zero. "
            "Reconciliation receipts are excluded. This is simulated supplier behavior, not carrier history."
        )
        if run is not None
        else "No reconstructed receipts are available, so no on-time rate is shown.",
        "items": items,
    }


def filter_options(conn: sqlite3.Connection) -> dict:
    run = _latest_run(conn)
    categories = [r["category"] for r in conn.execute("SELECT DISTINCT category FROM products WHERE is_active=1 ORDER BY category")]
    suppliers_rows = conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()
    products = conn.execute(
        "SELECT id, sku, name, category FROM products WHERE is_active=1 ORDER BY name"
    ).fetchall()
    years: list[int] = []
    months: list[str] = []
    date_min = None
    date_max = None
    if run is not None:
        span = conn.execute(
            """
            SELECT MIN(snapshot_date) AS a, MAX(snapshot_date) AS b
            FROM inventory_daily_snapshots WHERE run_id=?
            """,
            (int(run["id"]),),
        ).fetchone()
        date_min = span["a"]
        date_max = span["b"]
        years = [
            int(r["y"])
            for r in conn.execute(
                """
                SELECT DISTINCT substr(snapshot_date, 1, 4) AS y
                FROM inventory_daily_snapshots WHERE run_id=? ORDER BY y
                """,
                (int(run["id"]),),
            )
        ]
        months = [
            r["m"]
            for r in conn.execute(
                """
                SELECT DISTINCT substr(snapshot_date, 1, 7) AS m
                FROM inventory_daily_snapshots WHERE run_id=? ORDER BY m
                """,
                (int(run["id"]),),
            )
        ]
    return {
        **_run_meta(run, ready=run is not None, conn=conn),
        "categories": categories,
        "suppliers": [{"id": int(r["id"]), "name": r["name"]} for r in suppliers_rows],
        "products": [
            {"id": int(r["id"]), "sku": r["sku"], "name": r["name"], "category": r["category"]} for r in products
        ],
        "years": years,
        "months": months,
        "date_min": date_min,
        "date_max": date_max,
    }


def _insights(
    conn: sqlite3.Connection,
    filters: Filters,
    run: sqlite3.Row,
    days: list[dict],
    months: list[dict],
) -> list[dict]:
    insights: list[dict] = []
    ranked = _ranked_products(conn, filters, int(run["id"]))
    if ranked:
        top = max(ranked, key=lambda r: (int(r["inventory_value_paise"] or 0), -int(r["product_id"])))
        insights.append(
            {
                "id": "largest-inventory-value",
                "text": (
                    f"{top['name']} ({top['sku']}) holds the largest period-end inventory value "
                    f"at {_inr(int(top['inventory_value_paise'] or 0))}."
                ),
            }
        )
        idle = [
            r
            for r in ranked
            if int(r["inventory_value_paise"] or 0) > 0 and int(r["revenue_paise"] or 0) == 0
        ]
        if idle:
            pick = max(idle, key=lambda r: (int(r["inventory_value_paise"]), -int(r["product_id"])))
            insights.append(
                {
                    "id": "stock-without-sales",
                    "text": (
                        f"{pick['name']} ({pick['sku']}) has {_inr(int(pick['inventory_value_paise']))} "
                        "of period-end inventory and no fulfilled sales in this window."
                    ),
                }
            )
        else:
            scored = [r for r in ranked if int(r["revenue_paise"] or 0) > 0 and int(r["inventory_value_paise"] or 0) > 0]
            if scored:
                pick = max(
                    scored,
                    key=lambda r: (int(r["inventory_value_paise"]) / int(r["revenue_paise"]), -int(r["product_id"])),
                )
                insights.append(
                    {
                        "id": "stock-versus-sales",
                        "text": (
                            f"{pick['name']} ({pick['sku']}) has period-end inventory of "
                            f"{_inr(int(pick['inventory_value_paise']))} against fulfilled revenue of "
                            f"{_inr(int(pick['revenue_paise']))}."
                        ),
                    }
                )
    categories = category_breakdown(conn, filters)["categories"]
    if categories:
        lead = categories[0]
        share = lead["value_share"]
        share_txt = f" ({share * 100:.1f}% of filtered inventory value)" if share is not None else ""
        insights.append(
            {
                "id": "category-value",
                "text": (
                    f"{lead['category']} holds the most period-end inventory value at "
                    f"{_inr(int(lead['inventory_value_paise']))}{share_txt}."
                ),
            }
        )
    changes = [m for m in months if m["absolute_change_paise"] is not None]
    if changes:
        jump = max(changes, key=lambda m: abs(int(m["absolute_change_paise"])))
        direction = "increase" if int(jump["absolute_change_paise"]) >= 0 else "decrease"
        insights.append(
            {
                "id": "largest-value-change",
                "text": (
                    f"{jump['month']} has the largest inventory-value {direction} in this window: "
                    f"{_inr(abs(int(jump['absolute_change_paise'])))} versus the previous month."
                ),
            }
        )
    if not insights and days:
        insights.append(
            {
                "id": "window",
                "text": f"The selected window has {len(days)} snapshot days and no ranked product breakdown.",
            }
        )
    return insights


def _inr(paise: int) -> str:
    return f"₹{paise / 100:,.0f}"


def live_inventory(conn: sqlite3.Connection, filters: Filters | None = None) -> dict:
    filters = filters or Filters()
    units, value = _live(conn, filters)
    return {
        "stock_units": units,
        "inventory_value_paise": value,
        "excess_inventory_value_paise": _excess(conn, filters),
        "excess_definition": EXCESS_DEFINITION,
    }


def reorder_calendar(conn: sqlite3.Connection) -> dict:
    items: list[dict] = []
    orders = conn.execute(
        """
        SELECT o.id, o.product_id, o.qty, o.status, o.reviewed_at, o.recommendation_id,
               p.sku, p.name AS product_name,
               r.expected_arrival_date, r.trace_id
        FROM reorders o
        JOIN products p ON p.id = o.product_id
        LEFT JOIN recommendations r ON r.id = o.recommendation_id
        WHERE o.status != 'rejected'
        ORDER BY o.created_at, o.id
        """
    ).fetchall()
    for order in orders:
        item = {
            "id": f"reorder-{order['id']}",
            "kind": "reorder",
            "product_id": int(order["product_id"]),
            "title": f"{order['product_name']} ({order['sku']})",
            "status": order["status"],
            "qty": int(order["qty"]),
            "trace_id": order["trace_id"],
        }
        if order["status"] == "received" and order["reviewed_at"]:
            item.update(
                {
                    "date": str(order["reviewed_at"])[:10],
                    "date_role": "actual",
                    "detail": "Actual receipt. Physical stock increased when this approved order was received.",
                    "limitation": None,
                }
            )
        elif order["expected_arrival_date"]:
            item.update(
                {
                    "date": str(order["expected_arrival_date"])[:10],
                    "date_role": "predicted",
                    "detail": "Predicted arrival from the linked recommendation. This is not a confirmed carrier booking.",
                    "limitation": "No separate planned delivery date is stored on the reorder.",
                }
            )
        else:
            item.update(
                {
                    "date": None,
                    "date_role": "unavailable",
                    "detail": "This reorder has no expected arrival date.",
                    "limitation": "No expected arrival date is recorded, so none was invented from the supplier lead time.",
                }
            )
        items.append(item)

    recommendations = conn.execute(
        """
        SELECT r.id, r.product_id, r.suggested_qty, r.expected_arrival_date, r.trace_id, p.sku, p.name
        FROM recommendations r
        JOIN products p ON p.id = r.product_id
        WHERE r.status IN ('open', 'proposed')
          AND NOT EXISTS (
            SELECT 1 FROM reorders o
            WHERE o.recommendation_id = r.id AND o.status != 'rejected'
          )
        ORDER BY r.id
        """
    ).fetchall()
    for rec in recommendations:
        item = {
            "id": f"recommendation-{rec['id']}",
            "kind": "recommendation",
            "product_id": int(rec["product_id"]),
            "title": f"{rec['name']} ({rec['sku']})",
            "status": "recommended",
            "qty": int(rec["suggested_qty"]),
            "trace_id": rec["trace_id"],
        }
        if rec["expected_arrival_date"]:
            item.update(
                {
                    "date": str(rec["expected_arrival_date"])[:10],
                    "date_role": "predicted",
                    "detail": "Predicted arrival stored on the open recommendation.",
                    "limitation": None,
                }
            )
        else:
            item.update(
                {
                    "date": None,
                    "date_role": "unavailable",
                    "detail": "This recommendation has no expected arrival date.",
                    "limitation": "No expected arrival date is recorded.",
                }
            )
        items.append(item)

    as_of = datetime.strptime(settings.demo_date, "%Y-%m-%d")
    risks = conn.execute(
        """
        SELECT p.id, p.sku, p.name, c.days_of_supply, c.risk_level
        FROM product_risk_cache c
        JOIN products p ON p.id = c.product_id
        WHERE c.risk_level = 'high' AND c.days_of_supply IS NOT NULL
        ORDER BY c.days_of_supply ASC, p.id ASC
        LIMIT 12
        """
    ).fetchall()
    for risk in risks:
        when = as_of + timedelta(days=int(round(float(risk["days_of_supply"]))))
        items.append(
            {
                "id": f"stockout-{risk['id']}",
                "kind": "stockout_watch",
                "product_id": int(risk["id"]),
                "title": f"{risk['name']} ({risk['sku']})",
                "status": risk["risk_level"],
                "qty": None,
                "trace_id": None,
                "date": when.date().isoformat(),
                "date_role": "predicted",
                "detail": "Predicted stockout window from forecast days of supply. Not a purchase-order date.",
                "limitation": None,
            }
        )
    dated = sorted((item for item in items if item["date"]), key=lambda item: (item["date"], item["id"]))
    undated = [item for item in items if not item["date"]]
    return {
        "items": dated + undated,
        "dated_count": len(dated),
        "undated_count": len(undated),
        "note": (
            "Actual dates are receipt timestamps. Predicted dates come from a stored recommendation "
            "arrival or from forecast days of supply. Orders without a stored arrival stay undated."
        ),
    }
