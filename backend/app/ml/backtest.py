"""Chronologically valid holdout backtests for baselines and demand agents.

Evaluation mode: rolling one-step-ahead on the chronological holdout window.
Features at date d use only information available at decision time (lags via
shift). The demand model is trained on the train split only; holdout rows are
scored without refitting. Multi-horizon recursive forecasts are available via
`recursive_horizon_eval` when needed.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import numpy as np
import pandas as pd

from app.ml import baselines, features, metrics, splits
from app.ml.features import FEATURE_COLUMNS, load_sales_dataframe


def aligned_records_from_panel(
    holdout: pd.DataFrame,
    predictions: np.ndarray,
    *,
    method: str,
    model_version: str = "n/a",
    horizon: int = 1,
    provenance: str = "SYNTHETIC_DEMO",
    forecast_origin: str | None = None,
) -> list[dict[str, Any]]:
    """Build aligned actual-vs-predicted records (one per holdout row)."""
    preds = np.asarray(predictions, dtype=float).reshape(-1)
    if len(preds) != len(holdout):
        raise ValueError(
            f"predictions length {len(preds)} != holdout rows {len(holdout)}"
        )
    records: list[dict[str, Any]] = []
    for pred, (_, row) in zip(preds, holdout.iterrows()):
        target_date = pd.Timestamp(row["sale_date"]).strftime("%Y-%m-%d")
        origin = forecast_origin or target_date
        records.append(
            {
                "product_id": int(row["product_id"]),
                "forecast_origin": origin,
                "target_date": target_date,
                "horizon": int(horizon),
                "actual": float(row["target_units"]),
                "prediction": float(pred),
                "model_version": model_version,
                "method": method,
                "provenance": provenance,
            }
        )
    return records


def evaluate_method_on_holdout(
    holdout: pd.DataFrame,
    predictions: np.ndarray,
    *,
    method: str,
) -> dict[str, Any]:
    y_true = holdout["target_units"].astype(float).values
    y_pred = np.asarray(predictions, dtype=float).reshape(-1)
    if len(y_pred) != len(y_true):
        raise ValueError("prediction/actual length mismatch")
    return {
        "method": method,
        "wape": metrics.wape(y_true, y_pred),
        "mae": metrics.mae(y_true, y_pred),
        "rmse": metrics.rmse(y_true, y_pred),
        "n": int(len(y_true)),
        "evaluation_mode": "rolling_one_step_holdout",
    }


def _baseline_predictions(sales: pd.DataFrame, holdout: pd.DataFrame, method: str) -> np.ndarray:
    """Point-in-time baseline for each holdout row using history strictly before target date."""
    preds: list[float] = []
    sales = sales.copy()
    sales["sale_date"] = pd.to_datetime(sales["sale_date"])
    by_pid = {pid: grp.sort_values("sale_date") for pid, grp in sales.groupby("product_id")}
    for _, row in holdout.iterrows():
        pid = int(row["product_id"])
        target = pd.Timestamp(row["sale_date"])
        grp = by_pid.get(pid)
        if grp is None or grp.empty:
            preds.append(0.0)
            continue
        hist = grp[grp["sale_date"] < target]["units"]
        if method == "seasonal_naive_7":
            preds.append(baselines.seasonal_naive_7(hist))
        else:
            preds.append(baselines.moving_average_28(hist))
    return np.asarray(preds, dtype=float)


def _demand_model_predictions(holdout: pd.DataFrame, agent) -> np.ndarray:
    cols = agent.metadata.get("feature_columns", FEATURE_COLUMNS)
    present = [c for c in cols if c in holdout.columns]
    x = holdout[present].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).values
    # Pad/truncate if schema drift
    expected = len(cols)
    if x.shape[1] < expected:
        pad = np.zeros((x.shape[0], expected - x.shape[1]))
        x = np.hstack([x, pad])
    elif x.shape[1] > expected:
        x = x[:, :expected]
    raw = agent.model.predict(x)
    return np.maximum(0.0, np.asarray(raw, dtype=float))


def recursive_horizon_eval(
    sales: pd.DataFrame,
    *,
    product_id: int,
    origin: pd.Timestamp,
    horizon: int,
    predict_fn,
) -> list[dict[str, Any]]:
    """Multi-step recursive forecast from a single origin without peeking at future actuals.

    ``predict_fn(history_units: pd.Series, as_of: pd.Timestamp) -> float`` returns next-day demand.
    """
    grp = sales[sales["product_id"] == product_id].sort_values("sale_date").copy()
    grp["sale_date"] = pd.to_datetime(grp["sale_date"])
    hist = grp[grp["sale_date"] <= origin]["units"].astype(float).tolist()
    future = grp[grp["sale_date"] > origin].head(horizon)
    records = []
    for i, (_, row) in enumerate(future.iterrows(), start=1):
        series = pd.Series(hist)
        pred = float(max(0.0, predict_fn(series, origin)))
        records.append(
            {
                "product_id": int(product_id),
                "forecast_origin": origin.strftime("%Y-%m-%d"),
                "target_date": pd.Timestamp(row["sale_date"]).strftime("%Y-%m-%d"),
                "horizon": i,
                "actual": float(row["units"]),
                "prediction": pred,
            }
        )
        hist.append(pred)  # recurse on predictions, not future actuals
    return records


def run_backtests(
    conn: sqlite3.Connection,
    *,
    max_products: int | None = None,
    include_series: bool = True,
) -> list[dict]:
    sales = load_sales_dataframe(conn)
    if sales.empty:
        return [
            {"method": m, "wape": None, "mae": None, "rmse": None, "n": 0}
            for m in ("seasonal_naive_7", "moving_average_28", "demand_only", "full_decision_system")
        ]

    if max_products is not None:
        pids = sorted(sales["product_id"].unique())[:max_products]
        sales = sales[sales["product_id"].isin(pids)].copy()

    feat = features.build_panel_features(sales)
    sp = splits.split_panel(feat)
    ho = sp.holdout
    if ho.empty:
        return [
            {"method": m, "wape": None, "mae": None, "rmse": None, "n": 0}
            for m in ("seasonal_naive_7", "moving_average_28", "demand_only", "full_decision_system")
        ]

    # Align holdout order once so all methods share identical dates/SKUs
    ho = ho.sort_values(["product_id", "sale_date"]).reset_index(drop=True)
    out: list[dict] = []

    for method in ("seasonal_naive_7", "moving_average_28"):
        preds = _baseline_predictions(sales, ho, method)
        row = evaluate_method_on_holdout(ho, preds, method=method)
        if include_series:
            row["series"] = aligned_records_from_panel(
                ho, preds, method=method, model_version="baseline"
            )
        row["holdout_start"] = sp.holdout_start
        row["holdout_end"] = sp.holdout_end
        out.append(row)

    # Demand agent: score holdout feature rows with train-only artifact
    demand_row: dict[str, Any]
    try:
        from app.agents.demand import DemandAgent

        agent = DemandAgent()
        agent.load()
        preds = _demand_model_predictions(ho, agent)
        demand_row = evaluate_method_on_holdout(ho, preds, method="demand_only")
        demand_row["model_version"] = agent.version or "loaded"
        if include_series:
            demand_row["series"] = aligned_records_from_panel(
                ho,
                preds,
                method="demand_only",
                model_version=demand_row["model_version"],
            )
    except FileNotFoundError:
        # Fallback to MA28 when no artifact
        preds = _baseline_predictions(sales, ho, "moving_average_28")
        demand_row = evaluate_method_on_holdout(ho, preds, method="demand_only")
        demand_row["note"] = "demand artifact missing; used moving_average_28"
        if include_series:
            demand_row["series"] = aligned_records_from_panel(
                ho, preds, method="demand_only", model_version="fallback_ma28"
            )
    demand_row["holdout_start"] = sp.holdout_start
    demand_row["holdout_end"] = sp.holdout_end
    out.append(demand_row)

    out.append(
        {
            "method": "full_decision_system",
            "wape": None,
            "mae": None,
            "rmse": None,
            "n": 0,
            "note": "business policy metrics via performance.evaluate (SIMULATED replay)",
        }
    )
    return out
