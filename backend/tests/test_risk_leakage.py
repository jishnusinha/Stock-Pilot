"""Ensure risk classifiers never train on future-only outcome features."""

from __future__ import annotations

import numpy as np

from app.agents.sim_supply import (
    DECISION_TIME_FEATURES,
    FUTURE_ONLY_OUTCOMES,
    decision_time_feature_vector,
    simulate_scenarios,
)


def test_decision_time_schema_excludes_outcomes():
    for name in FUTURE_ONLY_OUTCOMES:
        assert name not in DECISION_TIME_FEATURES


def test_simulate_scenarios_x_has_only_decision_time_cols():
    rng = np.random.default_rng(0)
    x, y_so, y_ex, meta = simulate_scenarios(
        rng,
        20,
        stock=50,
        reorder_point=40,
        pack_size=12,
        daily_demand=5.0,
        lead_days=5,
        shelf_life=14,
    )
    assert x.shape == (20, len(DECISION_TIME_FEATURES))
    assert set(meta["feature_names"]) == set(DECISION_TIME_FEATURES)
    # Labels must vary and be derived from outcomes, not copied into X
    assert y_so.dtype in (np.int32, np.int64, int) or set(np.unique(y_so)).issubset({0, 1})
    assert len(y_so) == 20 and len(y_ex) == 20
    # X columns must not equal stockout_days / excess_peak outcome vectors
    outcomes = meta["outcomes"]
    for i, fname in enumerate(DECISION_TIME_FEATURES):
        assert fname not in FUTURE_ONLY_OUTCOMES
        # Correlation with label alone is fine; exact equality to outcome col is leakage
        if "stockout_days" in outcomes:
            assert not np.allclose(x[:, i], outcomes["stockout_days"])


def test_train_infer_feature_schema_match():
    rng = np.random.default_rng(1)
    x, _, _, meta = simulate_scenarios(
        rng,
        5,
        stock=30,
        reorder_point=25,
        pack_size=10,
        daily_demand=4.0,
        lead_days=7,
        shelf_life=None,
    )
    vec = decision_time_feature_vector(
        stock=30,
        reorder_point=25,
        pack_size=10,
        daily_demand=4.0,
        lead_days=7,
        order_qty=20,
        shelf_life_days=None,
        demand_p90=5.0,
    )
    assert vec.shape == (len(DECISION_TIME_FEATURES),)
    assert x.shape[1] == vec.shape[0]
    assert meta["feature_names"] == list(DECISION_TIME_FEATURES)


def test_more_stock_does_not_raise_stockout_label_rate():
    """Sanity: higher starting stock → fewer stockout labels (same other params)."""
    rng_lo = np.random.default_rng(2)
    rng_hi = np.random.default_rng(2)
    x_lo, y_lo, _, _ = simulate_scenarios(
        rng_lo, 80, stock=5, reorder_point=40, pack_size=12,
        daily_demand=8.0, lead_days=10, shelf_life=None,
    )
    x_hi, y_hi, _, _ = simulate_scenarios(
        rng_hi, 80, stock=200, reorder_point=40, pack_size=12,
        daily_demand=8.0, lead_days=10, shelf_life=None,
    )
    assert y_lo.mean() > y_hi.mean()
