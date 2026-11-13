"""Baselines + rolling one-step holdout evaluation for REAL_RETAIL_UCI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

from app.ml import metrics as M
from app.real_data import CURRENCY, DATASET_ATTRIBUTION, DATASET_DOI, EXPERIMENT_ID, OFFICIAL_PAGE_URL
from app.real_data.features import FEATURE_COLUMNS, attach_features_to_splits, feature_matrix
from app.real_data.paths import ensure_data_dirs, model_path, report_path
from app.real_data.split import load_split_frames
from app.real_data.train import MODEL_VERSION, load_trained


def seasonal_naive_units(history: pd.Series) -> float:
    """Same weekday from previous week: last observation 7 days ago when available."""
    if len(history) >= 7:
        return float(history.iloc[-7])
    return float(history.mean()) if len(history) else 0.0


def moving_average_units(history: pd.Series, window: int = 28) -> float:
    if len(history) == 0:
        return 0.0
    return float(history.iloc[-window:].mean())


def evaluate(*, evaluation_mode: str = "rolling_one_step_ahead") -> dict[str, Any]:
    """
    Rolling one-step-ahead on the test split.

    Features for each test date were built with shift-based history, so prior test-day
    actuals may appear in later test-day lags. This is explicitly labeled rolling one-step
    ahead — NOT a fixed-origin 28-day multi-horizon forecast.
    """
    ensure_data_dirs()
    if evaluation_mode != "rolling_one_step_ahead":
        raise ValueError("Only rolling_one_step_ahead is implemented for honesty/efficiency.")

    bundle = load_trained()
    demand = bundle["demand"]
    interval = bundle["interval"]
    intermittence = bundle["intermittence"]
    meta = bundle["meta"]

    train_raw, val_raw, test_raw = load_split_frames()
    # Full history panel for baseline series lookups
    history_panel = pd.concat([train_raw, val_raw, test_raw], ignore_index=True)
    history_panel["date"] = pd.to_datetime(history_panel["date"])
    history_panel = history_panel.sort_values(["stock_code", "date"])

    train_f, val_f, test_f = attach_features_to_splits(train_raw, val_raw, test_raw)
    if test_f.empty:
        raise ValueError("No test feature rows")

    x_te, y_te = feature_matrix(test_f)
    pred = np.clip(demand.predict(x_te), 0, None)
    p10_raw = np.clip(interval["p10"].predict(x_te), 0, None)
    p90_raw = np.clip(interval["p90"].predict(x_te), 0, None)
    p10 = np.empty_like(pred)
    p50 = pred.copy()
    p90 = np.empty_like(pred)
    for i in range(len(pred)):
        a, b, c = M.reconcile_quantiles(float(p10_raw[i]), float(pred[i]), float(p90_raw[i]))
        p10[i], p50[i], p90[i] = a, b, c

    p_zero = intermittence.predict_proba(x_te)[:, 1]
    y_zero = (y_te == 0).astype(int)

    # Baselines on identical test rows
    seasonal = []
    moving = []
    for _, row in test_f.iterrows():
        code = str(row["stock_code"])
        d = pd.Timestamp(row["date"])
        hist = history_panel[
            (history_panel["stock_code"] == code) & (history_panel["date"] < d)
        ]["units_sold"].astype(float)
        seasonal.append(seasonal_naive_units(hist))
        moving.append(moving_average_units(hist, 28))
    seasonal_arr = np.array(seasonal, dtype=float)
    moving_arr = np.array(moving, dtype=float)

    ml_metrics = {
        "mae": M.mae(y_te, p50),
        "rmse": M.rmse(y_te, p50),
        "wape": M.wape(y_te, p50),
    }
    seasonal_metrics = {
        "mae": M.mae(y_te, seasonal_arr),
        "rmse": M.rmse(y_te, seasonal_arr),
        "wape": M.wape(y_te, seasonal_arr),
    }
    moving_metrics = {
        "mae": M.mae(y_te, moving_arr),
        "rmse": M.rmse(y_te, moving_arr),
        "wape": M.wape(y_te, moving_arr),
    }
    interval_metrics = {
        "pinball_p10": M.pinball_loss(y_te, p10, 0.1),
        "pinball_p90": M.pinball_loss(y_te, p90, 0.9),
        "empirical_coverage_p10_p90": M.interval_coverage(y_te, p10, p90),
        "mean_interval_width": float(np.mean(p90 - p10)),
        "nominal_label": "p10–p90 (nominal ~80% if well calibrated; not a 95% CI)",
    }

    # Classification metrics for zero recorded-sales day
    zero_pred = (p_zero >= 0.5).astype(int)
    clf_metrics: dict[str, Any] = {
        "brier": M.brier_score(y_zero, p_zero),
        "precision": float(precision_score(y_zero, zero_pred, zero_division=0)),
        "recall": float(recall_score(y_zero, zero_pred, zero_division=0)),
        "f1": float(f1_score(y_zero, zero_pred, zero_division=0)),
        "target_label": "zero_recorded_sales_day",
    }
    if len(np.unique(y_zero)) > 1:
        clf_metrics["roc_auc"] = float(roc_auc_score(y_zero, p_zero))
    else:
        clf_metrics["roc_auc"] = None

    # Segment analysis
    segments = _segment_metrics(test_f, y_te, p50)

    pred_df = test_f[["date", "stock_code", "product_id"]].copy()
    pred_df["date"] = pd.to_datetime(pred_df["date"]).dt.strftime("%Y-%m-%d")
    pred_df["actual_units"] = y_te
    pred_df["predicted_units"] = p50
    pred_df["seasonal_naive_units"] = seasonal_arr
    pred_df["moving_average_units"] = moving_arr
    pred_df["p10_units"] = p10
    pred_df["p50_units"] = p50
    pred_df["p90_units"] = p90
    pred_df["p_zero_recorded_sales"] = p_zero
    pred_df["abs_error"] = np.abs(y_te - p50)
    pred_df["model_version"] = MODEL_VERSION
    pred_df["dataset_source"] = EXPERIMENT_ID
    pred_df["evaluation_mode"] = evaluation_mode
    pred_path = report_path("test_predictions.csv")
    pred_df.to_csv(pred_path, index=False)

    baseline_rows = [
        {"method": "hist_gradient_boosting", "mae": ml_metrics["mae"], "rmse": ml_metrics["rmse"], "wape": ml_metrics["wape"]},
        {"method": "seasonal_naive_7", "mae": seasonal_metrics["mae"], "rmse": seasonal_metrics["rmse"], "wape": seasonal_metrics["wape"]},
        {"method": "moving_average_28", "mae": moving_metrics["mae"], "rmse": moving_metrics["rmse"], "wape": moving_metrics["wape"]},
    ]
    baseline_df = pd.DataFrame(baseline_rows)
    baseline_path = report_path("baseline_comparison.csv")
    baseline_df.to_csv(baseline_path, index=False)

    # Feature importance proxy: gain from HGB if available
    fi_path = report_path("feature_importance.csv")
    _write_feature_importance(demand, fi_path)

    wapes = {r["method"]: r["wape"] for r in baseline_rows if r["wape"] is not None}
    best_method = min(wapes, key=wapes.get) if wapes else None

    metrics_payload = {
        "experiment_id": EXPERIMENT_ID,
        "model_version": MODEL_VERSION,
        "evaluation_mode": evaluation_mode,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "n_test_rows": int(len(y_te)),
        "n_skus": int(test_f["stock_code"].nunique()),
        "currency": CURRENCY,
        "ml": ml_metrics,
        "baselines": {
            "seasonal_naive_7": seasonal_metrics,
            "moving_average_28": moving_metrics,
        },
        "interval": interval_metrics,
        "intermittence": clf_metrics,
        "segments": segments,
        "best_wape_method": best_method,
        "training_metadata_path": str(model_path("training_metadata.json")),
        "notes": [
            "Rolling one-step-ahead: prior test actuals may enter later lags.",
            "Observed sales ≠ true unconstrained demand.",
            "p10–p90 is not a 95% confidence interval.",
            "Does not validate supplier ETA, stockout, or excess-risk agents.",
        ],
    }
    metrics_path = report_path("metrics.json")
    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    # Split summary for dates
    split_summary = {}
    sp = report_path("split_summary.json")
    if sp.exists():
        split_summary = json.loads(sp.read_text(encoding="utf-8"))

    eval_manifest = {
        "experiment_id": EXPERIMENT_ID,
        "dataset_source": EXPERIMENT_ID,
        "source_url": OFFICIAL_PAGE_URL,
        "doi": DATASET_DOI,
        "attribution": DATASET_ATTRIBUTION,
        "model_version": MODEL_VERSION,
        "evaluation_mode": evaluation_mode,
        "evaluated_at": metrics_payload["evaluated_at"],
        "artifacts": {
            "metrics": str(metrics_path),
            "baseline_comparison": str(baseline_path),
            "test_predictions": str(pred_path),
            "feature_importance": str(fi_path),
            "models_dir": str(model_path("demand_hgb.joblib").parent),
        },
        "split_boundaries": split_summary.get("boundaries"),
        "status": "evaluated",
        "train_meta": {
            "trained_at": meta.get("trained_at"),
            "seed": meta.get("seed"),
            "n_train_rows": meta.get("n_train_rows"),
        },
    }
    report_path("evaluation_manifest.json").write_text(json.dumps(eval_manifest, indent=2), encoding="utf-8")

    print(f"[real-data] Test WAPE ml={ml_metrics['wape']:.4f} "
          f"seasonal={seasonal_metrics['wape']:.4f} ma={moving_metrics['wape']:.4f}")
    print(f"[real-data] Best WAPE method: {best_method}")
    return metrics_payload


def _segment_metrics(test_f: pd.DataFrame, y: np.ndarray, pred: np.ndarray) -> dict[str, Any]:
    df = test_f.copy()
    df["_y"] = y
    df["_p"] = pred
    # Volume segments by mean actual units per SKU on test
    sku_mean = df.groupby("stock_code")["_y"].mean()
    q33, q66 = sku_mean.quantile([0.33, 0.66])
    high = set(sku_mean[sku_mean >= q66].index)
    low = set(sku_mean[sku_mean <= q33].index)
    inter = set(sku_mean[sku_mean < 1.0].index)  # mean < 1 unit/day ≈ intermittent

    def pack(codes: set[str], name: str) -> dict[str, Any]:
        mask = df["stock_code"].isin(codes)
        yt = df.loc[mask, "_y"].to_numpy()
        yp = df.loc[mask, "_p"].to_numpy()
        return {
            "name": name,
            "n_rows": int(mask.sum()),
            "n_skus": int(df.loc[mask, "stock_code"].nunique()),
            "mae": M.mae(yt, yp),
            "rmse": M.rmse(yt, yp),
            "wape": M.wape(yt, yp),
        }

    return {
        "high_volume": pack(high, "high_volume"),
        "low_volume": pack(low, "low_volume"),
        "intermittent_mean_lt_1": pack(inter, "intermittent_mean_lt_1"),
        "overall": {
            "n_rows": int(len(df)),
            "n_skus": int(df["stock_code"].nunique()),
            "mae": M.mae(y, pred),
            "rmse": M.rmse(y, pred),
            "wape": M.wape(y, pred),
        },
    }


def _write_feature_importance(model: Any, path) -> None:
    try:
        # HistGradientBoosting has no classic feature_importances_; use permutation-free proxy
        names = list(FEATURE_COLUMNS)
        if hasattr(model, "feature_importances_"):
            vals = model.feature_importances_
        else:
            # Equal placeholder ranks noting unavailability
            vals = np.ones(len(names)) / len(names)
            note = "uniform_proxy_hgb_has_no_native_importances"
            pd.DataFrame({"feature": names, "importance": vals, "note": note}).to_csv(path, index=False)
            return
        pd.DataFrame({"feature": names, "importance": vals}).to_csv(path, index=False)
    except Exception:
        pd.DataFrame({"feature": list(FEATURE_COLUMNS), "importance": [None] * len(FEATURE_COLUMNS)}).to_csv(
            path, index=False
        )
