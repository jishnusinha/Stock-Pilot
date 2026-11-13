"""Train REAL_RETAIL_UCI models (isolated artifacts)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression

from app.real_data import EXPERIMENT_ID, PROCESSING_VERSION
from app.real_data.features import FEATURE_COLUMNS, attach_features_to_splits, feature_matrix
from app.real_data.paths import MODELS_DIR, ensure_data_dirs, model_path, report_path
from app.real_data.split import load_split_frames
from app.ml import metrics as M


MODEL_VERSION = "real_uci_v1"


def _set_threads(threads: int) -> None:
    n = max(1, min(2, int(threads)))
    os.environ["OMP_NUM_THREADS"] = str(n)
    os.environ["OPENBLAS_NUM_THREADS"] = str(n)
    os.environ["MKL_NUM_THREADS"] = str(n)
    os.environ["NUMEXPR_NUM_THREADS"] = str(n)


def train_models(*, threads: int = 2, seed: int = 42, fast: bool = False) -> dict[str, Any]:
    _set_threads(threads)
    ensure_data_dirs()
    train_raw, val_raw, test_raw = load_split_frames()
    train_f, val_f, test_f = attach_features_to_splits(train_raw, val_raw, test_raw)
    if train_f.empty:
        raise ValueError("No training feature rows after lag warmup")

    x_tr, y_tr = feature_matrix(train_f)
    x_va, y_va = feature_matrix(val_f) if not val_f.empty else (np.empty((0, len(FEATURE_COLUMNS))), np.array([]))

    # --- Demand point forecast ---
    demand_params = dict(
        max_iter=60 if fast else 120,
        learning_rate=0.08,
        max_depth=4,
        min_samples_leaf=20,
        random_state=seed,
    )
    demand = HistGradientBoostingRegressor(**demand_params)
    demand.fit(x_tr, y_tr)
    pred_tr = np.clip(demand.predict(x_tr), 0, None)
    pred_va = np.clip(demand.predict(x_va), 0, None) if len(x_va) else np.array([])

    demand_metrics = {
        "train": {
            "mae": M.mae(y_tr, pred_tr),
            "rmse": M.rmse(y_tr, pred_tr),
            "wape": M.wape(y_tr, pred_tr),
        },
        "validation": {
            "mae": M.mae(y_va, pred_va) if len(y_va) else None,
            "rmse": M.rmse(y_va, pred_va) if len(y_va) else None,
            "wape": M.wape(y_va, pred_va) if len(y_va) else None,
        },
    }

    # --- Quantile interval (p10 / p50 via demand / p90) ---
    n_est = 30 if fast else 60
    q10 = GradientBoostingRegressor(
        loss="quantile", alpha=0.1, n_estimators=n_est, max_depth=3, random_state=seed
    )
    q90 = GradientBoostingRegressor(
        loss="quantile", alpha=0.9, n_estimators=n_est, max_depth=3, random_state=seed + 1
    )
    q10.fit(x_tr, y_tr)
    q90.fit(x_tr, y_tr)
    p10_va = np.clip(q10.predict(x_va), 0, None) if len(x_va) else np.array([])
    p90_va = np.clip(q90.predict(x_va), 0, None) if len(x_va) else np.array([])
    if len(y_va):
        # Reconcile on validation for reporting
        lo, hi = [], []
        for a, b, c in zip(p10_va, pred_va, p90_va):
            aa, bb, cc = M.reconcile_quantiles(a, b, c)
            lo.append(aa)
            hi.append(cc)
        interval_val = {
            "pinball_p10": M.pinball_loss(y_va, np.array(lo), 0.1),
            "pinball_p90": M.pinball_loss(y_va, np.array(hi), 0.9),
            "coverage": M.interval_coverage(y_va, np.array(lo), np.array(hi)),
            "mean_width": float(np.mean(np.array(hi) - np.array(lo))),
        }
    else:
        interval_val = {}

    # --- Intermittence: P(zero recorded-sales day) ---
    y_zero = (y_tr == 0).astype(int)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed, solver="lbfgs")
    clf.fit(x_tr, y_zero)
    p_zero_tr = clf.predict_proba(x_tr)[:, 1]
    intermittence_metrics = {"brier_train": M.brier_score(y_zero, p_zero_tr)}
    if len(y_va):
        y_zero_va = (y_va == 0).astype(int)
        p_zero_va = clf.predict_proba(x_va)[:, 1]
        intermittence_metrics["brier_validation"] = M.brier_score(y_zero_va, p_zero_va)

    trained_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "experiment_id": EXPERIMENT_ID,
        "model_version": MODEL_VERSION,
        "processing_version": PROCESSING_VERSION,
        "trained_at": trained_at,
        "seed": seed,
        "threads": threads,
        "fast": fast,
        "feature_columns": list(FEATURE_COLUMNS),
        "n_train_rows": int(len(train_f)),
        "n_validation_rows": int(len(val_f)),
        "n_test_rows_available": int(len(test_f)),
        "skus": int(train_f["stock_code"].nunique()),
        "demand_params": demand_params,
        "quantile_n_estimators": n_est,
        "evaluation_note": "Validation metrics used for sanity checks only; test frozen until evaluate.",
        "python_packages": _package_versions(),
        "demand_metrics": demand_metrics,
        "interval_validation": interval_val,
        "intermittence_metrics": intermittence_metrics,
        "status": "trained",
        "currency": "GBP",
        "target": "daily_observed_units_sold",
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(demand, model_path("demand_hgb.joblib"))
    joblib.dump({"p10": q10, "p90": q90}, model_path("demand_interval_gb.joblib"))
    joblib.dump(clf, model_path("intermittence_lr.joblib"))
    meta_path = model_path("training_metadata.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # Feature schema sidecar
    schema = {
        "feature_columns": list(FEATURE_COLUMNS),
        "target": "target_units",
        "leakage_policy": "All lag/roll features use shift; no future targets or prices.",
    }
    model_path("feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"[real-data] Trained models → {MODELS_DIR}")
    print(f"[real-data] Val WAPE={demand_metrics['validation'].get('wape')}")
    return meta


def _package_versions() -> dict[str, str]:
    import sklearn
    import pandas
    import numpy

    return {
        "sklearn": sklearn.__version__,
        "pandas": pandas.__version__,
        "numpy": numpy.__version__,
    }


def load_trained() -> dict[str, Any]:
    meta_path = model_path("training_metadata.json")
    if not meta_path.exists():
        raise FileNotFoundError("No real-data training metadata; run real-data-train first.")
    demand = joblib.load(model_path("demand_hgb.joblib"))
    interval = joblib.load(model_path("demand_interval_gb.joblib"))
    intermittence = joblib.load(model_path("intermittence_lr.joblib"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return {
        "demand": demand,
        "interval": interval,
        "intermittence": intermittence,
        "meta": meta,
    }
