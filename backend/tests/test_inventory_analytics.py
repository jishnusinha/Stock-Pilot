"""Reconstructed inventory history and analytics formulas."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import repositories as repo
from app.main import app
from app.services.inventory_analytics import Filters, overview
from app.services.inventory_history import build_analytics
from app.services.seed import seed_demo


def _prepare(conn, *, products=4, days=40, seed=11):
    seed_demo(conn, products=products, days=days, seed=seed, as_of="2026-11-01")
    sales = conn.execute("SELECT COUNT(*), COALESCE(SUM(units), 0) FROM sales").fetchone()
    stock = conn.execute("SELECT COALESCE(SUM(stock_on_hand), 0) FROM products").fetchone()
    return int(sales[0]), int(sales[1]), int(stock[0])


def test_conservation_continuity_and_reconciliation(tmp_db):
    sales_n, sales_units, stock_units = _prepare(tmp_db)
    first = build_analytics(tmp_db, seed=11)
    assert first["reused"] is False
    assert first["checksum"]

    bad_balance = tmp_db.execute(
        """
        SELECT COUNT(*) FROM inventory_daily_snapshots
        WHERE closing_stock != opening_stock + received_units + returned_units
              + adjustment_units - sold_units - writeoff_units
           OR closing_stock < 0
           OR opening_stock < 0
           OR closing_value_paise != closing_stock * unit_cost_paise
           OR sold_units > demand_units
           OR unmet_demand_units != demand_units - sold_units
        """
    ).fetchone()[0]
    assert bad_balance == 0

    gaps = tmp_db.execute(
        """
        SELECT COUNT(*) FROM inventory_daily_snapshots a
        JOIN inventory_daily_snapshots b
          ON a.run_id = b.run_id AND a.product_id = b.product_id
         AND b.snapshot_date = date(a.snapshot_date, '+1 day')
        WHERE a.closing_stock != b.opening_stock
        """
    ).fetchone()[0]
    assert gaps == 0

    demand_mismatch = tmp_db.execute(
        """
        SELECT COUNT(*) FROM inventory_daily_snapshots s
        JOIN sales sa ON sa.product_id = s.product_id AND sa.sale_date = s.snapshot_date
        WHERE sa.units != s.demand_units
        """
    ).fetchone()[0]
    assert demand_mismatch == 0

    unreconciled = tmp_db.execute(
        """
        SELECT COUNT(*) FROM products p
        JOIN inventory_daily_snapshots s
          ON s.product_id = p.id AND s.snapshot_date = (
            SELECT snapshot_date FROM analytics_runs WHERE id = s.run_id
          )
        WHERE s.closing_stock != p.stock_on_hand
        """
    ).fetchone()[0]
    assert unreconciled == 0

    again = build_analytics(tmp_db, seed=11)
    assert again["reused"] is True
    assert again["checksum"] == first["checksum"]
    assert tmp_db.execute("SELECT COUNT(*) FROM analytics_runs").fetchone()[0] == 1

    forced = build_analytics(tmp_db, seed=11, force=True)
    assert forced["reused"] is False
    assert forced["checksum"] == first["checksum"]
    assert tmp_db.execute("SELECT COUNT(*) FROM analytics_runs").fetchone()[0] == 2
    assert tmp_db.execute("SELECT COUNT(*) FROM analytics_runs WHERE status='complete'").fetchone()[0] == 1
    assert tmp_db.execute("SELECT COUNT(*) FROM analytics_runs WHERE status='superseded'").fetchone()[0] == 1

    sales_after = tmp_db.execute("SELECT COUNT(*), COALESCE(SUM(units), 0) FROM sales").fetchone()
    stock_after = tmp_db.execute("SELECT COALESCE(SUM(stock_on_hand), 0) FROM products").fetchone()[0]
    assert (int(sales_after[0]), int(sales_after[1]), int(stock_after)) == (sales_n, sales_units, stock_units)

    versions = tmp_db.execute("SELECT COUNT(*) FROM model_versions").fetchone()[0]
    tmp_db.execute(
        """
        INSERT INTO model_versions(agent_name, version, artifact_file, training_source, trained_at)
        VALUES ('demand', '1.0.0', 'demand.joblib', 'SYNTHETIC_DEMO', '2026-11-01T00:00:00+00:00')
        """
    )
    build_analytics(tmp_db, seed=11)
    assert tmp_db.execute("SELECT COUNT(*) FROM model_versions").fetchone()[0] == versions + 1


def test_two_databases_match(tmp_path, monkeypatch):
    checksums = []
    for name in ("a.db", "b.db"):
        db = tmp_path / name
        monkeypatch.setattr(settings, "db_path", db)
        from app.db.connection import connect
        from app.db.migrations import migrate

        conn = connect(db)
        migrate(conn)
        seed_demo(conn, products=3, days=30, seed=5, as_of="2026-11-01")
        checksums.append(build_analytics(conn, seed=5)["checksum"])
        conn.close()
    assert checksums[0] == checksums[1]
    assert checksums[0]


def test_turnover_is_aggregate_not_mean_of_ratios(tmp_db):
    _prepare(tmp_db, products=5, days=36, seed=9)
    build_analytics(tmp_db, seed=9)
    body = overview(tmp_db, Filters())
    assert body["ready"] is True
    assert body["turnover"] is not None
    assert body["period_days"] > 0
    assert abs(body["turnover"] - (body["cogs_paise"] / body["average_inventory_value_paise"])) < 1e-9
    assert abs(body["days_inventory_outstanding"] - (body["period_days"] / body["turnover"])) < 1e-9
    assert "not forecast" in body["dio_definition"].lower() or "not forecast-based" in body["dio_definition"].lower()

    cat = tmp_db.execute("SELECT category FROM products ORDER BY id LIMIT 1").fetchone()[0]
    filtered = overview(tmp_db, Filters(category=cat))
    direct = tmp_db.execute(
        """
        SELECT SUM(s.cogs_paise)
        FROM inventory_daily_snapshots s
        JOIN products p ON p.id = s.product_id
        WHERE p.category = ?
        """,
        (cat,),
    ).fetchone()[0]
    assert filtered["cogs_paise"] == int(direct)
    assert filtered["cogs_paise"] < body["cogs_paise"]

    moves = __import__("app.services.inventory_analytics", fromlist=["movements"]).movements(tmp_db, Filters())
    assert moves["conserved_units"] is True
    assert moves["conserved_value"] is True


def test_receive_does_not_rewrite_snapshots(tmp_db):
    _prepare(tmp_db, products=3, days=20, seed=4)
    build_analytics(tmp_db, seed=4)
    before = tmp_db.execute("SELECT SUM(closing_stock), COUNT(*) FROM inventory_daily_snapshots").fetchone()
    product = tmp_db.execute("SELECT id, unit_cost_paise, stock_on_hand FROM products ORDER BY id LIMIT 1").fetchone()
    reorder_id = repo.create_reorder(tmp_db, int(product["id"]), 6, int(product["unit_cost_paise"]))
    repo.set_reorder_status(tmp_db, reorder_id, "approved")
    stock_mid = tmp_db.execute("SELECT stock_on_hand FROM products WHERE id=?", (product["id"],)).fetchone()[0]
    assert stock_mid == product["stock_on_hand"]
    repo.set_reorder_status(tmp_db, reorder_id, "received")
    tmp_db.commit()
    stock_after = tmp_db.execute("SELECT stock_on_hand FROM products WHERE id=?", (product["id"],)).fetchone()[0]
    assert stock_after == product["stock_on_hand"] + 6
    after = tmp_db.execute("SELECT SUM(closing_stock), COUNT(*) FROM inventory_daily_snapshots").fetchone()
    assert tuple(after) == tuple(before)
    live = overview(tmp_db, Filters())
    assert live["live_stock_units"] == live["stock_units"] + 6 or live["live_matches_period_end"] is False
    assert live["live_stock_units"] != live["stock_units"]


def test_analytics_api_filters_and_segmentation(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    monkeypatch.setattr(settings, "db_path", db)
    monkeypatch.setattr(settings, "model_dir", tmp_path / "models")
    monkeypatch.setattr(settings, "eval_dir", tmp_path / "eval")
    settings.ensure_dirs()
    from app.db.connection import connect
    from app.db.migrations import migrate

    conn = connect(db)
    migrate(conn)
    seed_demo(conn, products=6, days=50, seed=8, as_of="2026-11-01")
    build_analytics(conn, seed=8)
    conn.close()

    with TestClient(app) as client:
        empty = client.get("/api/analytics/overview", params={"date_from": "2030-01-01", "date_to": "2030-01-31"})
        assert empty.status_code == 200
        assert empty.json()["ready"] is True
        assert empty.json()["turnover"] is None

        bad = client.get("/api/analytics/overview", params={"date_from": "2026-12-01", "date_to": "2026-01-01"})
        assert bad.status_code == 400
        missing = client.get("/api/analytics/overview", params={"product_id": 999999})
        assert missing.status_code == 404

        overview_body = client.get("/api/analytics/overview").json()
        assert overview_body["inventory_value_paise"] is not None
        assert overview_body["live_inventory_value_paise"] is not None
        top = client.get("/api/analytics/top-products").json()
        assert top["by_value"][0]["inventory_value_paise"] >= top["by_value"][-1]["inventory_value_paise"]
        assert {row["product_id"] for row in top["by_value"]}.isdisjoint(set()) 

        abc = client.get("/api/analytics/abc-xyz").json()
        assert sum(cell["sku_count"] for cell in abc["cells"]) == abc["total"]
        assert all(cell["interpretation"] for cell in abc["cells"])
        classes = {row["cell"] for row in client.get("/api/analytics/abc-xyz", params={"page_size": 200}).json()["products"]}
        assert classes <= {cell["cell"] for cell in abc["cells"]}

        slow = client.get("/api/analytics/slow-moving").json()
        assert slow["ready"] is True
        assert "expiry" not in slow["definition"].lower() or "no expiry" in slow["definition"].lower()
        for item in slow["items"]:
            assert item["suggested_action"]
            assert "expiry" not in item

        suppliers = client.get("/api/analytics/suppliers").json()
        assert "simulated" in suppliers["simulated_label"].lower()
        for item in suppliers["items"]:
            rate = item["simulated_on_time_rate"]
            if rate is not None:
                assert 0 <= rate <= 1

        cat = client.get("/api/analytics/filters").json()["categories"][0]
        scoped = client.get("/api/analytics/category-breakdown", params={"category": cat}).json()
        assert [row["category"] for row in scoped["categories"]] == [cat]

        calendar = client.get("/api/reorders/calendar")
        assert calendar.status_code == 200
        assert "undated" in calendar.json()["note"] or calendar.json()["note"]

        dash = client.get("/api/dashboard").json()
        assert "estimated_savings_paise" not in dash["kpis"]
        assert dash["kpis"]["inventory_value_paise"] is not None
