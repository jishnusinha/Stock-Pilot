"""Assemble Command Center payload from DB + cached forecasts."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from app.core.config import settings
from app.db import repositories as repo


def build_dashboard(conn: sqlite3.Connection) -> dict:
    as_of = settings.demo_date
    agg = repo.dashboard_aggregates(conn)

    # Aggregate 28-day projected revenue from risk cache + prices
    rev_row = conn.execute(
        """
        SELECT COALESCE(SUM(COALESCE(r.forecast_28d, 0) * p.selling_price_paise), 0)
        FROM products p
        LEFT JOIN product_risk_cache r ON r.product_id = p.id
        WHERE p.is_active = 1
        """
    ).fetchone()
    projected_rev = int(rev_row[0] or 0)

    # Simulated savings proxy from open recommendations cost vs naive 2x order
    sav_row = conn.execute(
        """
        SELECT COALESCE(SUM(estimated_cost_paise), 0)
        FROM recommendations WHERE status IN ('open','proposed')
        """
    ).fetchone()
    suggested_spend = int(sav_row[0] or 0)
    # Label clearly as simulation — use 15% of suggested spend as illustrative avoided waste proxy only if recs exist
    savings = int(suggested_spend * 0.12) if suggested_spend else None

    kpis = {
        "projected_revenue_paise": projected_rev,
        "at_risk_products": agg["high_risk"],
        "suggested_reorders": agg["open_recommendations"],
        "estimated_savings_paise": savings,
        "savings_label": "Simulation estimate" if savings is not None else "N/A",
        "projected_revenue_trend_pct": None,
        "at_risk_delta": None,
        "reorders_trend_pct": None,
        "savings_trend_pct": None,
    }

    forecast_series = _aggregate_forecast_series(conn, as_of)
    top_risk = _top_risk(conn, limit=8)
    alerts = _alerts(top_risk)
    recommendation = _top_recommendation(conn)

    return {
        "kpis": kpis,
        "forecast_series": forecast_series,
        "alerts": alerts,
        "top_risk": top_risk,
        "recommendation": recommendation,
        "data_source": "SYNTHETIC_DEMO",
        "as_of": as_of,
    }


def _aggregate_forecast_series(conn: sqlite3.Connection, as_of: str) -> list[dict]:
    """History (storewide units) + aggregated p10/p50/p90 forecast."""
    start_hist = (datetime.fromisoformat(as_of) - timedelta(days=55)).date().isoformat()
    hist = conn.execute(
        """
        SELECT sale_date AS d, SUM(units) AS u
        FROM sales
        WHERE sale_date >= ? AND sale_date <= ?
        GROUP BY sale_date
        ORDER BY sale_date
        """,
        (start_hist, as_of),
    ).fetchall()
    series: list[dict] = [
        {
            "date": r["d"],
            "actual": float(r["u"]),
            "p50": None,
            "p10": None,
            "p90": None,
            "is_forecast": False,
        }
        for r in hist
    ]

    fc = conn.execute(
        """
        SELECT target_date,
               SUM(p10_units) AS p10,
               SUM(p50_units) AS p50,
               SUM(p90_units) AS p90
        FROM forecasts
        WHERE as_of_date = ?
        GROUP BY target_date
        ORDER BY target_date
        """,
        (as_of,),
    ).fetchall()
    for r in fc:
        series.append(
            {
                "date": r["target_date"],
                "actual": None,
                "p50": float(r["p50"] or 0),
                "p10": float(r["p10"] or 0),
                "p90": float(r["p90"] or 0),
                "is_forecast": True,
            }
        )
    return series


def _top_risk(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    rows = conn.execute(
        """
        SELECT p.id AS product_id, p.sku, p.name, p.category, p.stock_on_hand AS current_stock,
               r.days_of_supply, r.forecast_28d AS forecast_4wk_units, r.risk_level
        FROM product_risk_cache r
        JOIN products p ON p.id = r.product_id
        WHERE r.risk_level IN ('high','medium')
        ORDER BY CASE r.risk_level WHEN 'high' THEN 0 ELSE 1 END,
                 COALESCE(r.days_of_supply, 999)
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _alerts(top_risk: list[dict]) -> list[dict]:
    alerts = []
    for i, r in enumerate(top_risk[:3]):
        dos = r.get("days_of_supply")
        severity = "critical" if r.get("risk_level") == "high" else "warning"
        title = "Stockout risk" if severity == "critical" else "Reorder soon"
        msg = f"{r['name']} (~{dos:.0f} days left)" if dos is not None else r["name"]
        alerts.append(
            {
                "id": f"alert-{r['product_id']}-{i}",
                "severity": severity,
                "title": title,
                "message": msg,
                "product_id": r["product_id"],
            }
        )
    return alerts


def _top_recommendation(conn: sqlite3.Connection) -> dict | None:
    rows = repo.get_open_recommendations(conn, limit=1)
    if not rows:
        return None
    r = rows[0]
    expl = {}
    try:
        expl = json.loads(r.get("explanation_json") or "{}")
    except json.JSONDecodeError:
        pass
    summary = expl.get("summary") or f"Reorder {r.get('product_name')} to reduce stockout risk."
    return {
        "id": r["id"],
        "product_id": r["product_id"],
        "title": f"Reorder {r.get('product_name')} ({r.get('sku')})",
        "message": summary,
        "suggested_qty": r["suggested_qty"],
        "impact_label": "ML recommendation",
    }
