"""Chronological train/validation/test splits and train-only SKU selection."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.real_data import EXPERIMENT_ID, PROCESSING_VERSION
from app.real_data.download import sha256_file
from app.real_data.paths import (
    MANIFEST_PATH,
    PROCESSED_DIR,
    SPLITS_DIR,
    ensure_data_dirs,
    report_path,
)

TEST_DAYS = 28
VAL_DAYS = 28
MIN_TRAIN_ACTIVE_DAYS = 30
MIN_TRAIN_UNITS = 50


def load_daily_sales() -> pd.DataFrame:
    path = PROCESSED_DIR / "daily_sales.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}; run real-data-prepare preprocess first.")
    df = pd.read_csv(path, dtype={"stock_code": str})
    df["date"] = pd.to_datetime(df["date"])
    return df


def densify_calendar(daily: pd.DataFrame, stock_codes: list[str]) -> pd.DataFrame:
    """
    Fill missing StockCode×date cells with zero observed sales for selected SKUs.

    Documented limitation: zeros mean no recorded transactions, not proven zero demand
    and not proof of store closure.
    """
    sub = daily[daily["stock_code"].isin(stock_codes)].copy()
    if sub.empty:
        return sub
    d0 = sub["date"].min()
    d1 = sub["date"].max()
    all_dates = pd.date_range(d0, d1, freq="D")
    # Description / product_id lookup
    meta = (
        sub.sort_values("date")
        .groupby("stock_code", as_index=False)
        .agg(product_id=("product_id", "last"), description=("description", "last"))
    )
    meta_map = meta.set_index("stock_code").to_dict(orient="index")
    frames = []
    for code in stock_codes:
        g = sub[sub["stock_code"] == code].set_index("date").sort_index()
        reindexed = g.reindex(all_dates)
        reindexed["stock_code"] = code
        reindexed["product_id"] = meta_map[code]["product_id"]
        reindexed["description"] = meta_map[code]["description"]
        reindexed["units_sold"] = reindexed["units_sold"].fillna(0.0)
        reindexed["sales_revenue_gbp"] = reindexed["sales_revenue_gbp"].fillna(0.0)
        reindexed["transaction_count"] = reindexed["transaction_count"].fillna(0).astype(int)
        # Forward-fill last known price only (no future price leakage); leave early NaN as NaN
        reindexed["representative_unit_price_gbp"] = reindexed["representative_unit_price_gbp"].ffill()
        reindexed["observed_sales_day"] = (
            reindexed["observed_sales_day"].astype("boolean").fillna(False).astype(bool)
        )
        # Days we invented as zeros were not original observed sale rows
        reindexed.loc[reindexed.index.difference(g.index), "observed_sales_day"] = False
        reindexed["data_source"] = EXPERIMENT_ID
        reindexed = reindexed.reset_index().rename(columns={"index": "date"})
        frames.append(reindexed)
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    return out.sort_values(["stock_code", "date"]).reset_index(drop=True)


def calendar_boundaries(dates: pd.DatetimeIndex) -> dict[str, pd.Timestamp]:
    """Final 28 calendar days = test; previous 28 = validation; earlier = train."""
    unique = pd.DatetimeIndex(sorted(pd.to_datetime(dates).unique()))
    if len(unique) < TEST_DAYS + VAL_DAYS + 7:
        raise ValueError(
            f"Insufficient calendar span ({len(unique)} days) for {TEST_DAYS}+{VAL_DAYS} holdout."
        )
    test_end = unique[-1]
    test_start = unique[-TEST_DAYS]
    # Use actual calendar day windows anchored at max date
    all_cal = pd.date_range(unique[0], unique[-1], freq="D")
    test_start = all_cal[-TEST_DAYS]
    test_end = all_cal[-1]
    val_end = test_start - pd.Timedelta(days=1)
    val_start = val_end - pd.Timedelta(days=VAL_DAYS - 1)
    train_end = val_start - pd.Timedelta(days=1)
    train_start = all_cal[0]
    return {
        "train_start": train_start,
        "train_end": train_end,
        "val_start": val_start,
        "val_end": val_end,
        "test_start": test_start,
        "test_end": test_end,
    }


def select_skus_train_only(
    daily: pd.DataFrame,
    bounds: dict[str, pd.Timestamp],
    *,
    max_products: int = 100,
    seed: int = 42,
) -> list[str]:
    """
    Select most consistently active physical SKUs using TRAINING WINDOW ONLY.

    Ranking: active days (units>0) descending, then total units, then stock_code.
    Deterministic; seed reserved for tie-breaking shuffle of equal ranks if needed.
    """
    train = daily[(daily["date"] >= bounds["train_start"]) & (daily["date"] <= bounds["train_end"])]
    if train.empty:
        raise ValueError("No training-period rows for SKU selection")
    stats = (
        train.groupby("stock_code")
        .agg(
            active_days=("units_sold", lambda s: int((s > 0).sum())),
            total_units=("units_sold", "sum"),
            n_rows=("units_sold", "size"),
        )
        .reset_index()
    )
    eligible = stats[
        (stats["active_days"] >= MIN_TRAIN_ACTIVE_DAYS) & (stats["total_units"] >= MIN_TRAIN_UNITS)
    ].copy()
    if eligible.empty:
        # Relax slightly if needed
        eligible = stats.sort_values(["active_days", "total_units"], ascending=False).head(max_products)
    else:
        eligible = eligible.sort_values(["active_days", "total_units", "stock_code"], ascending=[False, False, True])
    # Deterministic subsample if more than max: take top by activity (no randomness needed)
    # Seed recorded for reproducibility protocol even when unused.
    _ = seed
    chosen = eligible.head(max_products)["stock_code"].astype(str).tolist()
    if not chosen:
        raise ValueError("SKU selection produced an empty list")
    return chosen


def assign_split(date: pd.Timestamp, bounds: dict[str, pd.Timestamp]) -> str:
    if date < bounds["train_start"] or date > bounds["test_end"]:
        return "out_of_range"
    if date <= bounds["train_end"]:
        return "train"
    if date <= bounds["val_end"]:
        return "validation"
    return "test"


def build_splits(
    *,
    max_products: int = 100,
    seed: int = 42,
) -> dict[str, Any]:
    ensure_data_dirs()
    daily = load_daily_sales()
    # Initial bounds from full cleaned calendar, then re-select SKUs on train only
    bounds = calendar_boundaries(daily["date"])
    selected = select_skus_train_only(daily, bounds, max_products=max_products, seed=seed)
    panel = densify_calendar(daily, selected)
    # Recompute bounds on densified panel (same end date)
    bounds = calendar_boundaries(panel["date"])
    panel["split"] = panel["date"].map(lambda d: assign_split(pd.Timestamp(d), bounds))
    panel = panel[panel["split"].isin(["train", "validation", "test"])].copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.strftime("%Y-%m-%d")

    # Assert chronological separation
    train = panel[panel["split"] == "train"]
    val = panel[panel["split"] == "validation"]
    test = panel[panel["split"] == "test"]
    assert train["date"].max() < val["date"].min(), "Train/val overlap"
    assert val["date"].max() < test["date"].min(), "Val/test overlap"

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    train_path = SPLITS_DIR / "train.csv"
    val_path = SPLITS_DIR / "validation.csv"
    test_path = SPLITS_DIR / "test.csv"
    # Features are added later; base columns for inspectable CSVs
    cols = [
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
        "split",
    ]
    train[cols].to_csv(train_path, index=False)
    val[cols].to_csv(val_path, index=False)
    test[cols].to_csv(test_path, index=False)

    def _stats(df: pd.DataFrame) -> dict[str, Any]:
        u = df["units_sold"].astype(float)
        return {
            "rows": int(len(df)),
            "skus": int(df["stock_code"].nunique()),
            "date_min": df["date"].min() if len(df) else None,
            "date_max": df["date"].max() if len(df) else None,
            "zero_sale_rate": float((u == 0).mean()) if len(df) else None,
            "total_units_sold": float(u.sum()) if len(df) else 0.0,
        }

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "processing_version": PROCESSING_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "split_policy": (
            f"Final {TEST_DAYS} calendar days = test; previous {VAL_DAYS} = validation; "
            "earlier densified dates = training. No random shuffling."
        ),
        "sku_selection": {
            "max_products": max_products,
            "seed": seed,
            "criteria": (
                f"Training-window only; require >= {MIN_TRAIN_ACTIVE_DAYS} active days "
                f"and >= {MIN_TRAIN_UNITS} units when possible; rank by active days then units."
            ),
            "selected_stock_codes": selected,
            "n_selected": len(selected),
        },
        "boundaries": {k: str(v.date()) for k, v in bounds.items()},
        "train": _stats(train),
        "validation": _stats(val),
        "test": _stats(test),
        "assertions": {
            "max_train_lt_min_val": True,
            "max_val_lt_min_test": True,
        },
        "unseen_sku_behavior": "SKU list fixed from train; validation/test use the same SKUs only.",
        "calendar_notes": [
            "Zeros after densification are reconstructed absence of recorded sales.",
            "December 2011 source coverage is incomplete.",
            "Target is observed sales, not true unconstrained demand.",
        ],
        "file_checksums": {
            "train": sha256_file(train_path),
            "validation": sha256_file(val_path),
            "test": sha256_file(test_path),
        },
        "file_sizes_bytes": {
            "train": train_path.stat().st_size,
            "validation": val_path.stat().st_size,
            "test": test_path.stat().st_size,
        },
    }
    out = report_path("split_summary.json")
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Update manifest
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    else:
        manifest = {}
    manifest["selected_skus"] = selected
    manifest["selected_sku_count"] = len(selected)
    manifest["train_validation_test_ranges"] = summary["boundaries"]
    manifest["split_row_counts"] = {
        "train": summary["train"]["rows"],
        "validation": summary["validation"]["rows"],
        "test": summary["test"]["rows"],
    }
    manifest["split_seed"] = seed
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[real-data] Splits written for {len(selected)} SKUs → {SPLITS_DIR}")
    return summary


def load_split_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = pd.read_csv(SPLITS_DIR / "train.csv", dtype={"stock_code": str})
    val = pd.read_csv(SPLITS_DIR / "validation.csv", dtype={"stock_code": str})
    test = pd.read_csv(SPLITS_DIR / "test.csv", dtype={"stock_code": str})
    for df in (train, val, test):
        df["date"] = pd.to_datetime(df["date"])
    return train, val, test
