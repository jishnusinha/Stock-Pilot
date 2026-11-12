from app.services.reorder_optimizer import OptimizeInput, optimize_reorder


def test_optimizer_pack_multiples():
    res = optimize_reorder(
        OptimizeInput(
            stock_on_hand=10,
            daily_demand=5.0,
            unit_cost_paise=1000,
            pack_size=12,
            lead_days=5,
            stockout_risk=0.4,
            excess_risk=0.2,
            budget_paise=200_000,
        )
    )
    assert res.suggested_qty % 12 == 0
    assert res.estimated_cost_paise == res.suggested_qty * 1000
