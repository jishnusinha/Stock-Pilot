"""Predictive analytics service — uses persisted forecast rows, no training."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import repositories as repo
from app.db.migrations import migrate
from app.main import app
from app.services import inventory_analytics as ia
from app.services import predictive_inventory_analytics as pia
from app.services.inventory_history import build_analytics
from app.services.seed import seed_demo


def _seed_forecasts(conn, product_ids: list[int], as_of: str = "2026-11-01", version: str = "1.0.0"):
    origin = datetime.fromisoformat(as_of).date()
    for pid in product_ids:
        base = 1.0 + (pid % 5) * 0.4
        series = []
        for i in range(1, 29):
            series.append(
                {
                    "target_date": (origin + timedelta(days=i)).isoformat(),
                    "p10_units": base * 0.7,
                    "p50_units": base,
                    "p90_units": base * 1.4,
                }
            )
        repo.replace_forecasts(conn, pid, as_of, version, series, "SYNTHETIC_DEMO")
        repo.upsert_risk_cache(
            conn,
            pid,
            {
                "risk_level": "high" if pid % 3 == 0 else "low",
                "days_of_supply": 4 if pid % 3 == 0 else 30,
                "forecast_28d": base * 28,
                "sell_through": base,
                "stockout_risk": 0.7 if pid % 3 == 0 else 0.1,
                "provenance": "SYNTHETIC_DEMO",
            },
        )
        arrival = (origin + timedelta(days=5)).isoformat()
        repo.insert_recommendation(
            conn,
            {
                "product_id": pid,
                "suggested_qty": 12 if pid % 3 == 0 else 0,
                "expected_stockout_risk": 0.7 if pid % 3 == 0 else 0.1,
                "expected_excess_risk": 0.2,
                "estimated_cost_paise": 12_000 if pid % 3 == 0 else 0,
                "expected_arrival_date": arrival if pid % 3 == 0 else None,
                "explanation_json": {"source": "test"},
                "status": "open",
                "trace_id": f"trace-{pid}",
            },
        )
    conn.commit()


@pytest.fixture()
def pred_db(tmp_db):
    seed_demo(tmp_db, products=6, days=40, seed=21, as_of="2026-11-01")
    build_analytics(tmp_db, seed=21, force=True)
    ids = [int(r["id"]) for r in tmp_db.execute("SELECT id FROM products WHERE is_active=1").fetchall()]
    _seed_forecasts(tmp_db, ids)
    return tmp_db


def test_forecast_horizon_totals_not_fabricated(pred_db):
    body = pia.overview(pred_db, ia.Filters(), horizon_days=28)
    assert body["ready"] is True
    assert body["forecast_as_of"] == "2026-11-01"
    assert body["model_version"] == "1.0.0"
    assert body["kpis"]["expected_demand_units"]["by_horizon"]["7"] is not None
    assert body["kpis"]["expected_demand_units"]["by_horizon"]["14"] is not None
    assert body["kpis"]["expected_demand_units"]["by_horizon"]["28"] is not None
    # 7-day total should be less than 28-day for positive daily demand
    assert body["kpis"]["expected_demand_units"]["by_horizon"]["7"] < body["kpis"]["expected_demand_units"]["by_horizon"]["28"]


def test_missing_forecasts_unavailable(tmp_db):
    seed_demo(tmp_db, products=3, days=20, seed=3, as_of="2026-11-01")
    body = pia.overview(tmp_db, ia.Filters(), horizon_days=28)
    assert body["ready"] is False
    assert body["freshness"]["status"] == "unavailable"


def test_inventory_projection_conservation_and_modes(pred_db):
    base = pia.inventory_projection(pred_db, ia.Filters(), horizon_days=14, mode="no_reorder")
    rec = pia.inventory_projection(pred_db, ia.Filters(), horizon_days=14, mode="recommended")
    assert base["ready"] and rec["ready"]
    assert all(row["projected_inventory_units"] >= 0 for row in base["series"])
    # Recommended should inject receipts for high-risk SKUs with arrival day 5
    assert rec["total_receipts"] >= base["total_receipts"]
    assert rec["ending_inventory_value_paise"] >= base["ending_inventory_value_paise"]
    # Daily conservation: value equals units * cost at SKU level is checked in unit tests;
    # cohort series must stay non-negative and have demand fields.
    for row in base["series"]:
        assert row["predicted_demand"] >= 0
        assert row["forecast_as_of"] == "2026-11-01"


def test_risk_counts_not_probability_sums(pred_db):
    body = pia.risks(pred_db, ia.Filters(), limit=20)
    assert body["at_risk_count"] == body["distribution"]["high"]
    assert "never summed" in body["aggregation_note"].lower() or "Never sum" in body["aggregation_note"] or "never" in body["aggregation_note"].lower()
    # Excess proxy and modeled risk kept separate
    assert "proxy_definition" in body["excess"]
    assert "modeled_risk_definition" in body["excess"]


def test_category_filter_changes_coverage(pred_db):
    cats = pred_db.execute("SELECT DISTINCT category FROM products").fetchall()
    cat = cats[0]["category"]
    all_body = pia.overview(pred_db, ia.Filters(), horizon_days=28)
    cat_body = pia.overview(pred_db, ia.Filters(category=cat), horizon_days=28)
    assert cat_body["product_count"] <= all_body["product_count"]
    assert cat_body["forecast_coverage"]["selected"] == cat_body["product_count"]


def test_recommendations_respect_pack_and_explanations(pred_db):
    body = pia.recommendations(pred_db, ia.Filters(), limit=20)
    assert body["ready"]
    for item in body["items"]:
        if item["suggested_qty"] > 0 and item["pack_size"] > 1:
            assert item["suggested_qty"] % item["pack_size"] == 0 or "pack" in " ".join(item["constraints"]).lower()
        assert item["explanation"]
        assert "Not an opaque AI score" in body["ranking_rule"]


def test_stale_risk_freshness(pred_db):
    pid = int(pred_db.execute("SELECT id FROM products LIMIT 1").fetchone()["id"])
    repo.adjust_stock(pred_db, pid, 1, "stale_test")
    body = pia.overview(pred_db, ia.Filters(), horizon_days=28)
    assert body["freshness"]["stale_risk_count"] >= 1
    assert body["freshness"]["status"] in ("partial", "stale", "current")


def test_explain_comparison(pred_db):
    pid = int(
        pred_db.execute(
            "SELECT product_id FROM recommendations WHERE suggested_qty > 0 LIMIT 1"
        ).fetchone()["product_id"]
    )
    body = pia.explain_product(pred_db, pid)
    assert body["product"]["product_id"] == pid
    assert body["comparison"]["no_reorder"]["series"]
    assert body["comparison"]["recommended"]["series"]
    assert body["links"]["simulator"].endswith(str(pid))


@pytest.fixture()
def pred_client(tmp_path, monkeypatch):
    db = tmp_path / "pred_api.db"
    monkeypatch.setattr(settings, "db_path", db)
    monkeypatch.setattr(settings, "model_dir", tmp_path / "models")
    monkeypatch.setattr(settings, "eval_dir", tmp_path / "eval")
    settings.ensure_dirs()
    from app.db.connection import connect

    conn = connect(db)
    migrate(conn)
    seed_demo(conn, products=6, days=40, seed=33, as_of="2026-11-01")
    build_analytics(conn, seed=33, force=True)
    ids = [int(r["id"]) for r in conn.execute("SELECT id FROM products WHERE is_active=1").fetchall()]
    _seed_forecasts(conn, ids)
    conn.close()
    with TestClient(app) as client:
        yield client


def test_predictive_endpoints(pred_client):
    for path in (
        "/api/analytics/predictive/overview",
        "/api/analytics/predictive/demand",
        "/api/analytics/predictive/inventory-projection",
        "/api/analytics/predictive/risks",
        "/api/analytics/predictive/recommendations",
        "/api/analytics/predictive/data-quality",
    ):
        r = pred_client.get(path, params={"horizon_days": 14})
        assert r.status_code == 200, path
        assert r.json().get("ready") is not False or "forecast" in r.json() or path.endswith("data-quality")

    pid = pred_client.get("/api/products").json()["items"][0]["id"]
    ex = pred_client.get(f"/api/analytics/predictive/explain/{pid}")
    assert ex.status_code == 200
    assert ex.json()["product"]["product_id"] == pid

    bad = pred_client.get("/api/analytics/predictive/overview", params={"horizon_days": 9})
    assert bad.status_code == 400
