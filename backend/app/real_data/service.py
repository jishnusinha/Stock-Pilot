"""Read-only accessors for REAL_RETAIL_UCI evaluation artifacts (API layer)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.real_data import (
    CURRENCY,
    DATASET_ATTRIBUTION,
    DATASET_DOI,
    DATASET_LICENSE,
    DATASET_NAME,
    EXPERIMENT_ID,
    OFFICIAL_PAGE_URL,
)
from app.real_data.paths import (
    DATA_ROOT,
    MANIFEST_PATH,
    PROCESSED_DIR,
    RAW_XLSX_PATH,
    REPORTS_DIR,
    SAMPLES_DIR,
    SPLITS_DIR,
    model_path,
    report_path,
)
from app.real_data.pipeline import status as pipeline_status


class RealDataUnavailable(Exception):
    """Raised when experiment artifacts are missing."""


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_status() -> dict[str, Any]:
    return pipeline_status()


def get_summary() -> dict[str, Any]:
    st = pipeline_status()
    metrics = _read_json(report_path("metrics.json"))
    quality = _read_json(report_path("data_quality.json"))
    split = _read_json(report_path("split_summary.json"))
    manifest = _read_json(MANIFEST_PATH)
    return {
        "experiment_id": EXPERIMENT_ID,
        "dataset_name": DATASET_NAME,
        "attribution": DATASET_ATTRIBUTION,
        "source_url": OFFICIAL_PAGE_URL,
        "doi": DATASET_DOI,
        "license": DATASET_LICENSE,
        "currency": CURRENCY,
        "ready": st.get("ready_for_ui", False),
        "status": st,
        "metrics": metrics,
        "data_quality": {
            "before": (quality or {}).get("before_cleaning"),
            "after": (quality or {}).get("after_cleaning"),
        }
        if quality
        else None,
        "split_summary": split,
        "manifest": manifest,
        "limitations": (manifest or {}).get("limitations")
        or [
            "Observed sales are not unconstrained true demand.",
            "No inventory or supplier ground truth in this dataset.",
        ],
    }


def get_metrics() -> dict[str, Any]:
    metrics = _read_json(report_path("metrics.json"))
    if not metrics:
        raise RealDataUnavailable("Real-data metrics not available. Run real-data-evaluate.")
    return metrics


def get_baselines() -> list[dict[str, Any]]:
    path = report_path("baseline_comparison.csv")
    if not path.exists():
        raise RealDataUnavailable("Baseline comparison not available.")
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


def get_predictions(
    *,
    stock_code: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 5000,
) -> dict[str, Any]:
    path = report_path("test_predictions.csv")
    if not path.exists():
        raise RealDataUnavailable("Test predictions not available.")
    df = pd.read_csv(path, dtype={"stock_code": str})
    if stock_code:
        df = df[df["stock_code"] == stock_code]
    if date_from:
        df = df[df["date"] >= date_from]
    if date_to:
        df = df[df["date"] <= date_to]
    total = int(len(df))
    limit = max(1, min(int(limit), 20000))
    df = df.head(limit)
    return {
        "experiment_id": EXPERIMENT_ID,
        "evaluation_mode": "rolling_one_step_ahead",
        "total_matching_rows": total,
        "returned_rows": int(len(df)),
        "limit": limit,
        "rows": df.to_dict(orient="records"),
    }


def get_products(*, limit: int = 200) -> dict[str, Any]:
    # Prefer SKUs present in predictions
    pred = report_path("test_predictions.csv")
    if pred.exists():
        df = pd.read_csv(pred, dtype={"stock_code": str})
        stats = (
            df.groupby("stock_code", as_index=False)
            .agg(
                n_days=("date", "nunique"),
                total_actual=("actual_units", "sum"),
                mae=("abs_error", "mean"),
            )
            .sort_values("total_actual", ascending=False)
        )
        return {
            "experiment_id": EXPERIMENT_ID,
            "products": stats.head(limit).to_dict(orient="records"),
        }
    products = PROCESSED_DIR / "products.csv"
    if not products.exists():
        raise RealDataUnavailable("Product list not available.")
    df = pd.read_csv(products, dtype={"stock_code": str}).head(limit)
    return {"experiment_id": EXPERIMENT_ID, "products": df.to_dict(orient="records")}


def get_metadata() -> dict[str, Any]:
    manifest = _read_json(MANIFEST_PATH) or {}
    train_meta = _read_json(model_path("training_metadata.json")) or {}
    eval_manifest = _read_json(report_path("evaluation_manifest.json")) or {}
    quality = _read_json(report_path("data_quality.json")) or {}
    return {
        "experiment_id": EXPERIMENT_ID,
        "dataset_name": DATASET_NAME,
        "source_url": OFFICIAL_PAGE_URL,
        "doi": DATASET_DOI,
        "license": DATASET_LICENSE,
        "attribution": DATASET_ATTRIBUTION,
        "currency": CURRENCY,
        "raw_xlsx_present": RAW_XLSX_PATH.exists(),
        "raw_columns": [
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
            "UnitPrice",
            "CustomerID",
            "Country",
        ],
        "daily_sales_columns": [
            "date",
            "product_id",
            "stock_code",
            "description",
            "units_sold",
            "sales_revenue_gbp",
            "representative_unit_price_gbp",
            "transaction_count",
            "observed_sales_day",
            "data_source",
        ],
        "manifest": manifest,
        "training": {
            "model_version": train_meta.get("model_version"),
            "trained_at": train_meta.get("trained_at"),
            "feature_columns": train_meta.get("feature_columns"),
            "seed": train_meta.get("seed"),
        },
        "evaluation": eval_manifest,
        "cleaning_counts": (quality.get("after_cleaning") if quality else None),
        "sample_paths": {
            "raw_sample": str(SAMPLES_DIR / "raw_sample.csv"),
            "daily_sales_sample": str(SAMPLES_DIR / "daily_sales_sample.csv"),
            "relative_data_root": str(DATA_ROOT),
        },
        "provenance_label": EXPERIMENT_ID,
        "synthetic_label": "SYNTHETIC_DEMO",
    }


def predictions_csv_bytes(
    *,
    stock_code: str | None = None,
    limit: int = 50000,
) -> tuple[bytes, str]:
    path = report_path("test_predictions.csv")
    if not path.exists():
        raise RealDataUnavailable("Test predictions not available.")
    df = pd.read_csv(path, dtype={"stock_code": str})
    if stock_code:
        df = df[df["stock_code"] == stock_code]
    df = df.head(max(1, min(int(limit), 100000)))
    return df.to_csv(index=False).encode("utf-8"), "real_retail_uci_test_predictions.csv"


def safe_sample_csv(kind: str) -> tuple[bytes, str]:
    allowed = {
        "raw": SAMPLES_DIR / "raw_sample.csv",
        "daily_sales": SAMPLES_DIR / "daily_sales_sample.csv",
        "train_head": SPLITS_DIR / "train.csv",
    }
    if kind not in allowed:
        raise ValueError("Invalid sample kind")
    path = allowed[kind]
    if not path.exists():
        raise RealDataUnavailable(f"Sample {kind} not available.")
    # Cap train_head to first 500 rows for safety
    if kind == "train_head":
        df = pd.read_csv(path, dtype={"stock_code": str}, nrows=500)
        return df.to_csv(index=False).encode("utf-8"), "train_sample.csv"
    return path.read_bytes(), path.name
