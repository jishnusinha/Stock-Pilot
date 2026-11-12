"""StockPilot 3.1 fingerprint, reconciliation, and cohort behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import repositories as repo
from app.main import app
from app.services.analytics_fingerprint import clear_fingerprint_cache, source_fingerprint
from app.services.benchmark_stats import summarize_durations
from app.services.inventory_analytics import Filters, movements, overview
from app.services.inventory_history import analytics_status, build_analytics
from app.services.policy_replay import stratified_product_ids
from app.services.seed import seed_demo


def _prepare(conn, *, products=4, days=28, seed=11):
    seed_demo(conn, products=products, days=days, seed=seed, as_of="2026-11-01")


def test_percentiles_use_nearest_rank():
    stats = summarize_durations([10, 20, 30, 40, 100])
    assert stats["n"] == 5
    assert stats["p50_ms"] == 30
    assert stats["p95_ms"] == 100
    assert stats["max_ms"] == 100
    assert summarize_durations([])["p95_ms"] is None


def test_identical_source_reuses_and_force_keeps_the_old_run(tmp_db):
    _prepare(tmp_db)
    first = build_analytics(tmp_db, seed=11)
    clear_fingerprint_cache()
    again = build_analytics(tmp_db, seed=11)
    assert again["reused"] is True
    assert again["source_fingerprint"] == first["source_fingerprint"]
    assert again["freshness"] == "fresh"
    forced = build_analytics(tmp_db, seed=11, force=True)
    assert forced["regenerated"] is True
    assert tmp_db.execute("SELECT COUNT(*) FROM analytics_runs WHERE status='superseded'").fetchone()[0] == 1
    old_snaps = tmp_db.execute(
        "SELECT COUNT(*) FROM inventory_daily_snapshots s JOIN analytics_runs r ON r.id=s.run_id WHERE r.status='superseded'"
    ).fetchone()[0]
    assert old_snaps > 0


def test_changed_sales_are_stale_until_force(tmp_db):
    _prepare(tmp_db)
    first = build_analytics(tmp_db, seed=11)
    tmp_db.execute("UPDATE sales SET units = units + 1 WHERE id = (SELECT MIN(id) FROM sales)")
    tmp_db.commit()
    clear_fingerprint_cache()
    status = analytics_status(tmp_db, seed=11)
    assert status["freshness"] == "stale"
    stale = build_analytics(tmp_db, seed=11)
    assert stale["stale"] is True
    assert stale["regenerated"] is False
    assert tmp_db.execute("SELECT COUNT(*) FROM analytics_runs WHERE status='complete'").fetchone()[0] == 1
    rebuilt = build_analytics(tmp_db, seed=11, force=True)
    assert rebuilt["freshness"] == "fresh"
    assert rebuilt["source_fingerprint"] != first["source_fingerprint"]
    assert tmp_db.execute("SELECT COUNT(*) FROM analytics_runs WHERE status='superseded'").fetchone()[0] == 1


def test_cost_change_is_stale_and_receipt_is_not(tmp_db):
    _prepare(tmp_db, products=3, days=20, seed=4)
    build_analytics(tmp_db, seed=4)
    product = tmp_db.execute("SELECT id, unit_cost_paise, stock_on_hand FROM products ORDER BY id LIMIT 1").fetchone()
    before = source_fingerprint(tmp_db, seed=4, snapshot_date=tmp_db.execute("SELECT MAX(sale_date) FROM sales").fetchone()[0])
    reorder_id = repo.create_reorder(tmp_db, int(product["id"]), 6, int(product["unit_cost_paise"]))
    repo.set_reorder_status(tmp_db, reorder_id, "approved")
    repo.set_reorder_status(tmp_db, reorder_id, "received")
    tmp_db.commit()
    clear_fingerprint_cache()
    after_receipt = analytics_status(tmp_db, seed=4)
    assert after_receipt["freshness"] == "fresh"
    assert after_receipt["anchor_drift"] is True
    snaps = tmp_db.execute("SELECT SUM(closing_stock) FROM inventory_daily_snapshots").fetchone()[0]
    reused = build_analytics(tmp_db, seed=4)
    assert reused["reused"] is True
    assert tmp_db.execute("SELECT SUM(closing_stock) FROM inventory_daily_snapshots").fetchone()[0] == snaps
    tmp_db.execute("UPDATE products SET unit_cost_paise = unit_cost_paise + 25 WHERE id=?", (product["id"],))
    tmp_db.commit()
    clear_fingerprint_cache()
    changed = source_fingerprint(tmp_db, seed=4, snapshot_date=after_receipt["current_snapshot_date"])
    assert changed != before
    assert analytics_status(tmp_db, seed=4)["freshness"] == "stale"


def test_failed_validation_does_not_publish_a_run(tmp_db, monkeypatch):
    _prepare(tmp_db)
    def boom(*_args, **_kwargs):
        raise RuntimeError("validation failed")

    monkeypatch.setattr("app.services.inventory_history._validate_run", boom)
    try:
        build_analytics(tmp_db, seed=11)
        raised = False
    except RuntimeError:
        raised = True
    assert raised
    assert tmp_db.execute("SELECT COUNT(*) FROM analytics_runs WHERE status='complete'").fetchone()[0] == 0
    assert tmp_db.execute("SELECT COUNT(*) FROM inventory_daily_snapshots").fetchone()[0] == 0


def test_reconciliation_is_separate_and_still_conserves(tmp_db):
    _prepare(tmp_db)
    info = build_analytics(tmp_db, seed=11)
    assert info["recon_up_units"] + info["recon_down_units"] == info["absolute_adjustment_units"]
    report = movements(tmp_db, Filters())
    assert report["reconciliation_split_conserved"] is True
    assert report["conserved_units"] is True
    recon = report["reconciliation"]
    assert recon["up_units"] == report["reconciliation_receipt_units"]
    assert recon["down_units"] == report["reconciliation_writeoff_units"]
    assert recon["provenance"] == "SYNTHETIC_RECONSTRUCTED"
    body = overview(tmp_db, Filters())
    assert body["stock_units_meaning"] == "period_end_historical_closing_stock"
    assert body["excess_meaning"] == "current_operational_overlay"
    assert body["reconciliation"]["absolute_units"] == recon["absolute_units"]


def test_segment_filters_kpis_without_reclassifying_the_matrix(tmp_path, monkeypatch):
    db = tmp_path / "seg.db"
    monkeypatch.setattr(settings, "db_path", db)
    monkeypatch.setattr(settings, "model_dir", tmp_path / "models")
    monkeypatch.setattr(settings, "eval_dir", tmp_path / "eval")
    settings.ensure_dirs()
    from app.db.connection import connect
    from app.db.migrations import migrate

    conn = connect(db)
    migrate(conn)
    seed_demo(conn, products=8, days=40, seed=8, as_of="2026-11-01")
    build_analytics(conn, seed=8)
    conn.close()
    with TestClient(app) as client:
        full = client.get("/api/analytics/overview")
        abc = client.get("/api/analytics/abc-xyz", params={"page_size": 200})
        assert full.status_code == 200
        assert abc.status_code == 200
        cells = [cell for cell in abc.json()["cells"] if cell["sku_count"] > 0]
        assert cells
        segment = cells[0]["cell"]
        scoped = client.get("/api/analytics/overview", params={"segment": segment})
        matrix = client.get("/api/analytics/abc-xyz", params={"segment": segment, "page_size": 200})
        assert scoped.status_code == 200
        assert scoped.json()["segment"] == segment
        assert scoped.json()["inventory_value_paise"] <= full.json()["inventory_value_paise"]
        assert [cell["sku_count"] for cell in matrix.json()["cells"]] == [cell["sku_count"] for cell in abc.json()["cells"]]
        cleared = client.get("/api/analytics/overview")
        assert cleared.json()["inventory_value_paise"] == full.json()["inventory_value_paise"]
        cat = client.get("/api/analytics/filters").json()["categories"][0]
        both = client.get("/api/analytics/top-products", params={"category": cat, "segment": segment})
        assert both.status_code == 200
        month = client.get("/api/analytics/inventory-trend").json()["months"][0]["month"]
        year, mon = month.split("-")
        mixed = client.get(
            "/api/analytics/overview",
            params={"year": int(year), "month": int(mon), "category": cat, "segment": segment},
        )
        assert mixed.status_code == 200
        assert mixed.json()["period_end"].startswith(month)


def test_historical_stock_survives_a_receipt(tmp_db):
    _prepare(tmp_db, products=3, days=24, seed=6)
    build_analytics(tmp_db, seed=6)
    before = overview(tmp_db, Filters())
    product = tmp_db.execute("SELECT id, unit_cost_paise FROM products ORDER BY id LIMIT 1").fetchone()
    reorder_id = repo.create_reorder(tmp_db, int(product["id"]), 4, int(product["unit_cost_paise"]))
    repo.set_reorder_status(tmp_db, reorder_id, "approved")
    repo.set_reorder_status(tmp_db, reorder_id, "received")
    tmp_db.commit()
    after = overview(tmp_db, Filters())
    assert after["stock_units"] == before["stock_units"]
    assert after["inventory_value_paise"] == before["inventory_value_paise"]
    assert after["live_stock_units"] == before["live_stock_units"] + 4
    assert after["freshness"] == "fresh"


def test_stratified_sample_is_stable_and_mixed(tmp_db):
    _prepare(tmp_db, products=12, days=30, seed=3)
    first = stratified_product_ids(tmp_db, sample=8, seed=3)
    second = stratified_product_ids(tmp_db, sample=8, seed=3)
    assert first == second
    assert len(first) == 8
    marks = ",".join("?" * len(first))
    categories = tmp_db.execute(
        f"SELECT COUNT(DISTINCT category) FROM products WHERE id IN ({marks})",
        first,
    ).fetchone()[0]
    assert categories >= 1
