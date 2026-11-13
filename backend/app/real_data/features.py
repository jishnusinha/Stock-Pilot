"""Leakage-safe feature engineering for REAL_RETAIL_UCI daily sales."""

from __future__ import annotations

import numpy as np
import pandas as pd

# Align with synthetic StockPilot lag/roll conventions where applicable
LAG_DAYS = (1, 7, 14, 28)
ROLL_WINDOWS = (7, 14, 28)

FEATURE_COLUMNS = (
    [f"lag_{d}" for d in LAG_DAYS]
    + [f"roll_mean_{w}" for w in ROLL_WINDOWS]
    + [f"roll_std_{w}" for w in ROLL_WINDOWS]
    + [
        "dow",
        "dom",
        "month",
        "week_of_year",
        "sin_dow",
        "cos_dow",
        "hist_zero_share_28",
        "hist_mean_28",
        "price_gbp",
        "price_vs_hist_median",
    ]
)


def build_sku_features(sku_df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-SKU features. Rolling stats use shift(1) so the prediction-day target is excluded.
    Price uses contemporaneous known representative price (from same-day sales or ffilled history);
    no future prices.
    """
    df = sku_df.sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"])
    y = df["units_sold"].astype(float)
    for lag in LAG_DAYS:
        df[f"lag_{lag}"] = y.shift(lag)
    shifted = y.shift(1)
    for w in ROLL_WINDOWS:
        df[f"roll_mean_{w}"] = shifted.rolling(w, min_periods=1).mean()
        df[f"roll_std_{w}"] = shifted.rolling(w, min_periods=1).std().fillna(0.0)
    df["dow"] = df["date"].dt.dayofweek.astype(int)
    df["dom"] = df["date"].dt.day.astype(int)
    df["month"] = df["date"].dt.month.astype(int)
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["sin_dow"] = np.sin(2 * np.pi * df["dow"] / 7.0)
    df["cos_dow"] = np.cos(2 * np.pi * df["dow"] / 7.0)
    # Historical zero-sale share and mean from prior 28 days only
    zero = (y == 0).astype(float)
    df["hist_zero_share_28"] = zero.shift(1).rolling(28, min_periods=1).mean()
    df["hist_mean_28"] = shifted.rolling(28, min_periods=1).mean()
    price = df["representative_unit_price_gbp"].astype(float)
    # Historical median price from prior observations only
    hist_med = price.shift(1).expanding(min_periods=1).median()
    df["price_gbp"] = price.fillna(hist_med).fillna(0.0)
    df["price_vs_hist_median"] = df["price_gbp"] / hist_med.replace(0, np.nan).fillna(1.0)
    df["target_units"] = y
    return df


def build_panel_features(panel: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for code, grp in panel.groupby("stock_code"):
        feat = build_sku_features(grp)
        feat["stock_code"] = str(code)
        parts.append(feat)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    # Drop rows lacking minimum lag history (lag_28)
    out = out.dropna(subset=["lag_28"])
    return out


def feature_matrix(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    x = df[cols].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    y = df["target_units"].astype(float).to_numpy()
    return x, y


def attach_features_to_splits(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build features on the concatenated panel so lag history crosses split boundaries,
    then re-slice by target-date split membership. This does NOT leak future targets:
    every feature uses only past units via shift.
    """
    panel = pd.concat([train, val, test], ignore_index=True)
    panel = panel.sort_values(["stock_code", "date"]).reset_index(drop=True)
    feat = build_panel_features(panel)
    # Preserve split label from target date
    feat["split"] = feat["split"] if "split" in feat.columns else None
    tr = feat[feat["split"] == "train"].copy()
    va = feat[feat["split"] == "validation"].copy()
    te = feat[feat["split"] == "test"].copy()
    return tr, va, te
