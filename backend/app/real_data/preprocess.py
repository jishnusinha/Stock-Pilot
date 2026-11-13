"""Convert UCI Online Retail XLSX → cleaned CSVs and daily SKU sales."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.real_data import (
    CURRENCY,
    DATASET_ATTRIBUTION,
    DATASET_DOI,
    DATASET_LICENSE,
    DATASET_NAME,
    EXPERIMENT_ID,
    OFFICIAL_PAGE_URL,
    PROCESSING_VERSION,
)
from app.real_data.download import require_raw_xlsx, sha256_file
from app.real_data.paths import (
    MANIFEST_PATH,
    PROCESSED_DIR,
    RAW_XLSX_PATH,
    SAMPLES_DIR,
    ensure_data_dirs,
    report_path,
)

RAW_COLUMNS = (
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
)

# Administrative / non-product stock codes commonly present in this dataset.
ADMIN_STOCKCODE_EXACT = {
    "POST",
    "DOT",
    "D",
    "M",
    "BANK CHARGES",
    "PADS",
    "CRUK",
    "AMAZONFEE",
    "B",
    "S",
    "m",
    "gift_0001_10",
    "gift_0001_20",
    "gift_0001_30",
    "gift_0001_40",
    "gift_0001_50",
}
ADMIN_PREFIXES = ("gift_",)
ADMIN_SUBSTRINGS = ("ADJUST", "TEST", "MANUAL")


def _is_admin_stock_code(code: str) -> bool:
    c = str(code).strip()
    if not c:
        return True
    if c.upper() in {x.upper() for x in ADMIN_STOCKCODE_EXACT}:
        return True
    lower = c.lower()
    if any(lower.startswith(p) for p in ADMIN_PREFIXES):
        return True
    if any(s.lower() in lower for s in ADMIN_SUBSTRINGS):
        return True
    # Purely alphabetic short codes (postage-like) excluding normal SKUs with letters
    if re.fullmatch(r"[A-Za-z]+", c) and len(c) <= 6:
        return True
    return False


def read_raw_transactions(xlsx_path: Path | None = None) -> pd.DataFrame:
    """Read the official workbook preserving InvoiceNo/StockCode as strings."""
    path = Path(xlsx_path) if xlsx_path else require_raw_xlsx()
    # openpyxl read_only keeps memory lower on 8 GB laptops
    df = pd.read_excel(
        path,
        engine="openpyxl",
        dtype={"InvoiceNo": str, "StockCode": str, "CustomerID": "float64"},
    )
    # Normalize column names to canonical set
    rename = {c: c.strip() for c in df.columns}
    df = df.rename(columns=rename)
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Workbook missing expected columns: {missing}")
    df = df[list(RAW_COLUMNS)].copy()
    df["InvoiceNo"] = df["InvoiceNo"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype(str).str.strip()
    # Preserve source timestamp; do not invent a timezone.
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    df["transaction_date"] = df["InvoiceDate"].dt.normalize()
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")
    return df


def audit_quality(df: pd.DataFrame) -> dict[str, Any]:
    inv = df["InvoiceNo"].astype(str)
    qty = df["Quantity"]
    price = df["UnitPrice"]
    cancel_mask = inv.str.upper().str.startswith("C", na=False)
    dates = df["InvoiceDate"].dropna()
    return {
        "total_source_rows": int(len(df)),
        "date_min": str(dates.min()) if len(dates) else None,
        "date_max": str(dates.max()) if len(dates) else None,
        "n_distinct_stock_codes": int(df["StockCode"].nunique(dropna=True)),
        "n_distinct_invoices": int(df["InvoiceNo"].nunique(dropna=True)),
        "missing_by_column": {c: int(df[c].isna().sum()) for c in RAW_COLUMNS},
        "cancellation_invoice_rows": int(cancel_mask.sum()),
        "negative_quantity_rows": int((qty < 0).sum()),
        "zero_quantity_rows": int((qty == 0).sum()),
        "nonpositive_price_rows": int((price <= 0).sum()),
        "missing_description_rows": int(df["Description"].isna().sum() + (df["Description"].astype(str).str.strip() == "").sum()),
        "missing_customer_id_rows": int(df["CustomerID"].isna().sum()),
        "exact_duplicate_rows": int(df.duplicated(keep=False).sum()),
        "admin_stock_code_rows": int(df["StockCode"].map(_is_admin_stock_code).sum()),
        "extreme_quantity_abs_gt_1000": int((qty.abs() > 1000).sum()),
        "null_invoice_date_rows": int(df["InvoiceDate"].isna().sum()),
        "currency": CURRENCY,
        "timezone_note": "Source timestamps have no guaranteed timezone; values kept as parsed local clock times.",
    }


def clean_transactions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """
    Split into positive sales vs returns/cancellations/excluded.

    Policy:
    - Cancellations (InvoiceNo starting with C) and negative quantities → returns audit set.
    - Do NOT subtract returns from unrelated sales dates.
    - Exclude admin/non-product StockCodes from forecasting.
    - Exclude nonpositive prices and zero/NaN quantities from sales.
    - Exact duplicates are kept (legitimate repeated invoice lines) but counted.
    """
    before = audit_quality(df)
    flags = pd.Series("keep_candidate", index=df.index, dtype=object)

    def _assign(mask: pd.Series, reason: str) -> None:
        """Assign reason only while still a keep_candidate (first matching rule wins)."""
        nonlocal flags
        flags = flags.mask((flags == "keep_candidate") & mask, reason)

    inv = df["InvoiceNo"].astype(str)
    _assign(inv.str.upper().str.startswith("C", na=False), "cancellation_invoice")
    _assign(df["Quantity"].isna(), "missing_quantity")
    _assign(df["Quantity"] == 0, "zero_quantity")
    _assign(df["Quantity"] < 0, "negative_quantity")
    _assign(df["UnitPrice"].isna() | (df["UnitPrice"] <= 0), "nonpositive_price")
    _assign(df["InvoiceDate"].isna(), "missing_invoice_date")
    _assign(df["StockCode"].map(_is_admin_stock_code), "admin_stock_code")
    # Missing description alone does not drop a row if StockCode is usable.
    sales_mask = flags == "keep_candidate"
    sales = df.loc[sales_mask].copy()
    sales["removal_reason"] = "kept_positive_sale"
    sales["units"] = sales["Quantity"].astype(float)
    sales["line_revenue_gbp"] = sales["units"] * sales["UnitPrice"].astype(float)

    returns = df.loc[~sales_mask].copy()
    returns["removal_reason"] = flags.loc[~sales_mask].values
    returns["units"] = returns["Quantity"].astype(float)
    returns["line_revenue_gbp"] = returns["units"] * returns["UnitPrice"].fillna(0).astype(float)

    after_sales = {
        "positive_sales_rows": int(len(sales)),
        "returns_or_excluded_rows": int(len(returns)),
        "removal_reason_counts": {k: int(v) for k, v in returns["removal_reason"].value_counts().items()},
        "distinct_sales_stock_codes": int(sales["StockCode"].nunique()),
        "date_min_sales": str(sales["transaction_date"].min()) if len(sales) else None,
        "date_max_sales": str(sales["transaction_date"].max()) if len(sales) else None,
        "duplicate_policy": "Exact duplicate invoice lines are retained; they can be legitimate repeated lines.",
        "return_matching_limitation": (
            "Returns are not uniquely matchable to original sales dates; "
            "they are audited separately and never treated as negative demand."
        ),
        "outlier_policy": "Large quantities are retained unless rows fail other explicit exclusion rules.",
    }
    quality = {
        "before_cleaning": before,
        "after_cleaning": after_sales,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "processing_version": PROCESSING_VERSION,
    }
    return sales, returns, quality


def aggregate_daily_sales(sales: pd.DataFrame) -> pd.DataFrame:
    """One row per StockCode × calendar date of observed fulfilled sales."""
    if sales.empty:
        return pd.DataFrame(
            columns=[
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
            ]
        )
    g = sales.groupby(["StockCode", "transaction_date"], as_index=False).agg(
        units_sold=("units", "sum"),
        sales_revenue_gbp=("line_revenue_gbp", "sum"),
        transaction_count=("InvoiceNo", "count"),
        description=("Description", "last"),
    )
    # Revenue-weighted average unit price when units > 0
    g["representative_unit_price_gbp"] = np.where(
        g["units_sold"] > 0,
        g["sales_revenue_gbp"] / g["units_sold"],
        np.nan,
    )
    # Stable integer product_id from sorted unique StockCodes (mapping only; not leakage)
    codes = sorted(g["StockCode"].unique().tolist())
    code_to_id = {c: i + 1 for i, c in enumerate(codes)}
    g["product_id"] = g["StockCode"].map(code_to_id)
    g["stock_code"] = g["StockCode"]
    g["date"] = pd.to_datetime(g["transaction_date"]).dt.strftime("%Y-%m-%d")
    g["observed_sales_day"] = True
    g["data_source"] = EXPERIMENT_ID
    out = g[
        [
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
        ]
    ].sort_values(["stock_code", "date"])
    return out.reset_index(drop=True)


def build_products_table(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame(columns=["product_id", "stock_code", "description", "n_days", "total_units"])
    return (
        daily.groupby(["product_id", "stock_code"], as_index=False)
        .agg(
            description=("description", "last"),
            n_days=("date", "nunique"),
            total_units=("units_sold", "sum"),
            total_revenue_gbp=("sales_revenue_gbp", "sum"),
        )
        .sort_values("total_units", ascending=False)
        .reset_index(drop=True)
    )


def write_sample(df: pd.DataFrame, path: Path, n: int = 200) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.head(n).to_csv(path, index=False)


def run_preprocess(*, xlsx_path: Path | None = None) -> dict[str, Any]:
    ensure_data_dirs()
    path = Path(xlsx_path) if xlsx_path else require_raw_xlsx()
    raw_sha = sha256_file(path)
    print(f"[real-data] Reading {path} …")
    raw = read_raw_transactions(path)
    write_sample(raw, SAMPLES_DIR / "raw_sample.csv", 200)

    print(f"[real-data] Cleaning {len(raw):,} source rows …")
    sales, returns, quality = clean_transactions(raw)
    sales_out = sales[
        [
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
            "UnitPrice",
            "CustomerID",
            "Country",
            "transaction_date",
            "units",
            "line_revenue_gbp",
            "removal_reason",
        ]
    ].copy()
    sales_out["transaction_date"] = pd.to_datetime(sales_out["transaction_date"]).dt.strftime("%Y-%m-%d")
    sales_csv = PROCESSED_DIR / "transactions_clean.csv"
    returns_csv = PROCESSED_DIR / "returns_summary.csv"
    sales_out.to_csv(sales_csv, index=False)
    returns[
        [
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
            "UnitPrice",
            "CustomerID",
            "Country",
            "removal_reason",
            "units",
            "line_revenue_gbp",
        ]
    ].to_csv(returns_csv, index=False)

    print("[real-data] Aggregating daily SKU sales …")
    daily = aggregate_daily_sales(sales)
    daily_csv = PROCESSED_DIR / "daily_sales.csv"
    daily.to_csv(daily_csv, index=False)
    write_sample(daily, SAMPLES_DIR / "daily_sales_sample.csv", 200)
    products = build_products_table(daily)
    products_csv = PROCESSED_DIR / "products.csv"
    products.to_csv(products_csv, index=False)

    quality_path = report_path("data_quality.json")
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    quality["files"] = {
        "transactions_clean_csv": str(sales_csv),
        "returns_summary_csv": str(returns_csv),
        "daily_sales_csv": str(daily_csv),
        "products_csv": str(products_csv),
        "raw_xlsx": str(path),
        "raw_sha256": raw_sha,
        "file_sizes_bytes": {
            "transactions_clean": sales_csv.stat().st_size,
            "returns_summary": returns_csv.stat().st_size,
            "daily_sales": daily_csv.stat().st_size,
            "products": products_csv.stat().st_size,
            "raw_xlsx": path.stat().st_size,
        },
    }
    quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")

    # Partial manifest (completed further in split stage)
    manifest = {
        "dataset_name": DATASET_NAME,
        "experiment_id": EXPERIMENT_ID,
        "source_url": OFFICIAL_PAGE_URL,
        "doi": DATASET_DOI,
        "license": DATASET_LICENSE,
        "attribution": DATASET_ATTRIBUTION,
        "currency": CURRENCY,
        "raw_file": str(RAW_XLSX_PATH),
        "raw_sha256": raw_sha,
        "processing_version": PROCESSING_VERSION,
        "processed_at": quality["processed_at"],
        "row_counts": {
            "source": quality["before_cleaning"]["total_source_rows"],
            "positive_sales": quality["after_cleaning"]["positive_sales_rows"],
            "returns_or_excluded": quality["after_cleaning"]["returns_or_excluded_rows"],
            "daily_sales": int(len(daily)),
            "products": int(len(products)),
        },
        "limitations": [
            "Observed sales are not unconstrained true demand.",
            "No store-opening calendar; zero-sale days after densification are reconstructed.",
            "No inventory on-hand or stockout ground truth.",
            "No supplier delivery timestamps.",
            "Returns are not matched to original sales.",
            "UnitPrice is GBP; never labeled as INR.",
            "December 2011 source period is incomplete.",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[real-data] Wrote quality report → {quality_path}")
    return {"quality": quality, "manifest": manifest, "daily_rows": int(len(daily))}
