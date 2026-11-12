"""Regression tests for chronological demand evaluation (no mean-holdout hack)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.backtest import (
    aligned_records_from_panel,
    evaluate_method_on_holdout,
    run_backtests,
)
from app.ml import features, splits
from app.services.seed import seed_demo
from app.agents.base import TrainContext
from app.agents.demand import DemandAgent


def _tiny_sales_panel() -> pd.DataFrame:
    """Deterministic panel: 2 products × 160 days (enough after lag warmup for holdout)."""
    rows = []
    for pid in (1, 2):
        for i, d in enumerate(pd.date_range("2026-01-01", periods=160, freq="D")):
            units = 10 + (i % 7) + pid
            rows.append(
                {
                    "product_id": pid,
                    "sale_date": d,
                    "units": float(units),
                    "selling_price_paise": 1000,
                    "promo_flag": 0,
                    "event_flag": 0,
                }
            )
    return pd.DataFrame(rows)


def test_holdout_actuals_are_daily_not_group_means():
    sales = _tiny_sales_panel()
    feat = features.build_panel_features(sales)
    sp = splits.split_panel(feat)
    assert not sp.holdout.empty

    records = aligned_records_from_panel(
        sp.holdout,
        predictions=sp.holdout["target_units"].astype(float).values,  # identity
        method="identity",
        model_version="test",
        horizon=1,
        provenance="SYNTHETIC_DEMO",
    )
    assert len(records) == len(sp.holdout)
    # Actuals must equal row-level units, not a repeated group mean
    for rec, (_, row) in zip(records, sp.holdout.iterrows()):
        assert rec["actual"] == float(row["target_units"])
        assert rec["product_id"] == int(row["product_id"])
        assert rec["target_date"] == pd.Timestamp(row["sale_date"]).strftime("%Y-%m-%d")


def test_demand_eval_does_not_repeat_single_prediction_vs_mean():
    """Catch the historical bug: one p50 vs mean(holdout) repeated N times."""
    sales = _tiny_sales_panel()
    feat = features.build_panel_features(sales)
    sp = splits.split_panel(feat)
    ho = sp.holdout
    assert len(ho) > 2

    # Fake a constant prediction equal to global mean — if eval compares to
    # per-row means incorrectly, WAPE collapses near zero despite bad alignment.
    mean_all = float(ho["target_units"].mean())
    preds = np.full(len(ho), mean_all)
    # Per-product means differ from global for our constructed series
    per_pid_means = ho.groupby("product_id")["target_units"].transform("mean").values
    assert not np.allclose(per_pid_means, ho["target_units"].values)

    result = evaluate_method_on_holdout(
        holdout=ho,
        predictions=preds,
        method="const_mean",
    )
    assert result["n"] == len(ho)
    # Metrics must be computed against genuine daily actuals
    y_true = ho["target_units"].astype(float).values
    expected_wape = float(np.sum(np.abs(y_true - preds)) / np.sum(np.abs(y_true)))
    assert abs(result["wape"] - expected_wape) < 1e-9
    # If someone compared preds to repeated means, WAPE would be near 0 for const=mean
    bogus = float(
        np.sum(np.abs(per_pid_means - preds)) / max(1e-9, np.sum(np.abs(per_pid_means)))
    )
    assert result["wape"] > bogus + 0.01 or not np.isclose(result["wape"], 0.0)


def test_baseline_and_demand_share_same_holdout_dates(tmp_db):
    seed_demo(tmp_db, products=4, days=160, seed=7)
    tmp_db.commit()
    agent = DemandAgent()
    agent.train(TrainContext(conn=tmp_db, fast=True, threads=1, version="test_bt"))
    results = run_backtests(tmp_db, max_products=4, include_series=True)
    by_method = {r["method"]: r for r in results}
    assert by_method["seasonal_naive_7"]["n"] > 0
    assert by_method["moving_average_28"]["n"] > 0
    assert by_method["demand_only"]["n"] > 0
    # Same evaluation set size for demand vs baselines (same SKUs/dates)
    assert by_method["demand_only"]["n"] == by_method["moving_average_28"]["n"]
    series = by_method["demand_only"].get("series") or []
    assert len(series) > 0
    assert "actual" in series[0] and "prediction" in series[0]
    # Actuals must vary across days (not a constant group mean)
    actuals = [r["actual"] for r in series]
    assert len(set(round(a, 4) for a in actuals)) > 1
