"""Reorder receive idempotency and stock-adjust stale marking."""

from app.db import repositories as repo
from app.services.seed import seed_demo


def test_receive_increments_stock_once(tmp_db):
    seed_demo(tmp_db, products=3, days=60, seed=9)
    tmp_db.commit()
    p = repo.get_product(tmp_db, 1)
    before = int(p["stock_on_hand"])
    rid = repo.create_reorder(
        tmp_db,
        product_id=1,
        qty=12,
        unit_cost_paise=int(p["unit_cost_paise"]),
        notes="test",
    )
    repo.set_reorder_status(tmp_db, rid, "approved")
    repo.set_reorder_status(tmp_db, rid, "received")
    mid = int(repo.get_product(tmp_db, 1)["stock_on_hand"])
    assert mid == before + 12
    # Duplicate receive must fail transition (already received)
    try:
        repo.set_reorder_status(tmp_db, rid, "received")
        assert False, "expected ValueError"
    except ValueError:
        pass
    after = int(repo.get_product(tmp_db, 1)["stock_on_hand"])
    assert after == mid


def test_adjust_stock_marks_risk_stale(tmp_db):
    seed_demo(tmp_db, products=3, days=60, seed=11)
    repo.upsert_risk_cache(
        tmp_db,
        1,
        {
            "risk_level": "high",
            "days_of_supply": 3,
            "forecast_28d": 10,
            "sell_through": 1,
            "stockout_risk": 0.8,
            "provenance": "SYNTHETIC_DEMO",
        },
    )
    tmp_db.commit()
    repo.adjust_stock(tmp_db, 1, 5, "manual_test")
    row = tmp_db.execute(
        "SELECT risk_level, provenance FROM product_risk_cache WHERE product_id=1"
    ).fetchone()
    assert "STALE_AFTER_STOCK_ADJUST" in (row["provenance"] or "")
