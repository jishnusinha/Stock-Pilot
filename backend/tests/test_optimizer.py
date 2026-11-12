from app.services.reorder_optimizer import OptimizeInput, optimize_reorder
from app.services.scenarios import ScenarioInput, simulate_stock_path


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


def test_zero_budget_forces_zero_qty():
    res = optimize_reorder(
        OptimizeInput(
            stock_on_hand=5,
            daily_demand=8.0,
            unit_cost_paise=1000,
            pack_size=12,
            lead_days=5,
            stockout_risk=0.9,
            excess_risk=0.1,
            budget_paise=0,
        )
    )
    assert res.suggested_qty == 0
    assert res.estimated_cost_paise == 0


def test_budget_less_than_one_pack_forces_zero():
    # pack cost = 12 * 1000 = 12000; budget 11999 → only 0
    res = optimize_reorder(
        OptimizeInput(
            stock_on_hand=5,
            daily_demand=8.0,
            unit_cost_paise=1000,
            pack_size=12,
            lead_days=5,
            stockout_risk=0.9,
            excess_risk=0.1,
            budget_paise=11_999,
        )
    )
    assert res.suggested_qty == 0


def test_exactly_one_pack_affordable():
    res = optimize_reorder(
        OptimizeInput(
            stock_on_hand=5,
            daily_demand=8.0,
            unit_cost_paise=1000,
            pack_size=12,
            lead_days=5,
            stockout_risk=0.9,
            excess_risk=0.1,
            budget_paise=12_000,
        )
    )
    assert res.suggested_qty in (0, 12)
    assert res.suggested_qty * 1000 <= 12_000


def test_candidate_risk_fn_can_change_selection():
    """When risk_fn heavily penalizes large qty, optimizer should prefer smaller qty."""
    base_kwargs = dict(
        stock_on_hand=40,
        daily_demand=3.0,
        unit_cost_paise=100,
        pack_size=10,
        lead_days=3,
        stockout_risk=0.2,
        excess_risk=0.2,
        budget_paise=50_000,
    )
    neutral = optimize_reorder(OptimizeInput(**base_kwargs, risk_fn=None))

    def penalize_large(qty: int) -> tuple[float, float]:
        # Huge excess risk for qty > 10
        if qty > 10:
            return 0.1, 0.99
        return 0.1, 0.01

    biased = optimize_reorder(OptimizeInput(**base_kwargs, risk_fn=penalize_large))
    assert biased.suggested_qty <= max(10, neutral.suggested_qty)
    assert biased.suggested_qty % 10 == 0


def test_path_tracks_unmet_demand():
    path = simulate_stock_path(
        ScenarioInput(
            stock_on_hand=0,
            daily_demand_p50=5.0,
            order_qty=0,
            lead_days=10,
            pack_size=1,
            horizon_days=4,
        )
    )
    assert path.stockout_days == 4
    assert path.unmet_demand_units == 20.0


def test_optimizer_deterministic():
    kwargs = dict(
        stock_on_hand=15,
        daily_demand=4.0,
        unit_cost_paise=500,
        pack_size=8,
        lead_days=4,
        stockout_risk=0.3,
        excess_risk=0.2,
        budget_paise=100_000,
    )
    a = optimize_reorder(OptimizeInput(**kwargs))
    b = optimize_reorder(OptimizeInput(**kwargs))
    assert a.suggested_qty == b.suggested_qty
    assert a.total_cost_score == b.total_cost_score
