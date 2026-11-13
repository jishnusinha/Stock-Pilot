"""Unit tests for deterministic inventory projection conservation rules."""

from app.services.inventory_projection import ReceiptEvent, day_index_for_date, project_inventory_path


def test_stock_never_negative_and_conservation():
    path = project_inventory_path(
        opening_stock=10,
        unit_cost_paise=100,
        as_of_date="2026-11-01",
        daily_demand=[4, 4, 4, 4, 4],
        mode="no_reorder",
    )
    assert all(day.closing_stock >= 0 for day in path.days)
    # Day 1: 10-4=6; day2: 6-4=2; day3: 2-4 → unmet 2, stock 0
    assert path.days[2].closing_stock == 0
    # Days 3–5: unmet 2 + 4 + 4 after stock depletes
    assert path.unmet_demand_units == 10.0
    assert path.ending_value_paise == 0


def test_receipt_on_modeled_day_changes_path():
    base = project_inventory_path(
        opening_stock=5,
        unit_cost_paise=200,
        as_of_date="2026-11-01",
        daily_demand=[3, 3, 3, 3],
        receipts=[],
        mode="no_reorder",
    )
    with_receipt = project_inventory_path(
        opening_stock=5,
        unit_cost_paise=200,
        as_of_date="2026-11-01",
        daily_demand=[3, 3, 3, 3],
        receipts=[ReceiptEvent(day_index=2, qty=12, source="recommended")],
        mode="recommended",
    )
    assert with_receipt.ending_stock > base.ending_stock
    assert with_receipt.days[1].receipts == 12
    assert with_receipt.total_receipts == 12


def test_projected_value_uses_unit_cost():
    path = project_inventory_path(
        opening_stock=10,
        unit_cost_paise=250,
        as_of_date="2026-11-01",
        daily_demand=[0, 0],
    )
    assert path.days[0].closing_value_paise == 2500
    assert path.ending_value_paise == 2500


def test_day_index_outside_horizon_is_none():
    assert day_index_for_date("2026-11-01", "2026-11-05", 28) == 4
    assert day_index_for_date("2026-11-01", "2026-11-01", 28) is None
    assert day_index_for_date("2026-11-01", "2027-01-01", 28) is None
