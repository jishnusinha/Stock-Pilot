"""End-to-end REAL_RETAIL_UCI pipeline orchestration."""

from __future__ import annotations

import json
from typing import Any

from app.real_data.download import download_official, import_local_xlsx, require_raw_xlsx, write_download_sidecar
from app.real_data.evaluate import evaluate
from app.real_data.paths import (
    MANIFEST_PATH,
    MODELS_DIR,
    PROCESSED_DIR,
    RAW_XLSX_PATH,
    REPORTS_DIR,
    SPLITS_DIR,
    ensure_data_dirs,
    report_path,
)
from app.real_data.preprocess import run_preprocess
from app.real_data.split import build_splits
from app.real_data.train import train_models


def status() -> dict[str, Any]:
    ensure_data_dirs()
    raw_ok = RAW_XLSX_PATH.exists()
    daily_ok = (PROCESSED_DIR / "daily_sales.csv").exists()
    splits_ok = (SPLITS_DIR / "train.csv").exists() and (SPLITS_DIR / "test.csv").exists()
    models_ok = (MODELS_DIR / "demand_hgb.joblib").exists()
    metrics_ok = report_path("metrics.json").exists()
    metrics = None
    if metrics_ok:
        metrics = json.loads(report_path("metrics.json").read_text(encoding="utf-8"))
    manifest = None
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        "experiment_id": "REAL_RETAIL_UCI",
        "raw_xlsx_present": raw_ok,
        "raw_xlsx_path": str(RAW_XLSX_PATH),
        "daily_sales_present": daily_ok,
        "splits_present": splits_ok,
        "models_present": models_ok,
        "metrics_present": metrics_ok,
        "ready_for_ui": bool(metrics_ok and splits_ok),
        "metrics_summary": {
            "wape": (metrics or {}).get("ml", {}).get("wape"),
            "mae": (metrics or {}).get("ml", {}).get("mae"),
            "rmse": (metrics or {}).get("ml", {}).get("rmse"),
            "best_wape_method": (metrics or {}).get("best_wape_method"),
            "evaluation_mode": (metrics or {}).get("evaluation_mode"),
            "model_version": (metrics or {}).get("model_version"),
        }
        if metrics
        else None,
        "selected_sku_count": (manifest or {}).get("selected_sku_count"),
        "split_ranges": (manifest or {}).get("train_validation_test_ranges"),
        "reports_dir": str(REPORTS_DIR),
        "models_dir": str(MODELS_DIR),
    }


def prepare(*, max_products: int = 100, seed: int = 42, xlsx_path=None) -> dict[str, Any]:
    require_raw_xlsx() if xlsx_path is None else None
    prep = run_preprocess(xlsx_path=xlsx_path)
    splits = build_splits(max_products=max_products, seed=seed)
    return {"preprocess": {"daily_rows": prep["daily_rows"]}, "splits": splits}


def run_all(
    *,
    max_products: int = 100,
    seed: int = 42,
    threads: int = 2,
    fast: bool = False,
    force_download: bool = False,
    skip_download: bool = False,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not skip_download:
        try:
            info = download_official(force=force_download)
            write_download_sidecar(info)
            out["download"] = info
        except RuntimeError as exc:
            if not RAW_XLSX_PATH.exists():
                raise
            out["download"] = {"status": "download_failed_using_local", "error": str(exc)}
    else:
        require_raw_xlsx()
        out["download"] = {"status": "skipped", "path": str(RAW_XLSX_PATH)}

    out["prepare"] = prepare(max_products=max_products, seed=seed)
    out["train"] = train_models(threads=threads, seed=seed, fast=fast)
    out["evaluate"] = evaluate()
    out["status"] = status()
    return out
