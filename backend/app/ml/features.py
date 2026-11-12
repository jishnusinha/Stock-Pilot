"""Temporal demand features without target leakage."""

from __future__ import annotations

import numpy as np
import pandas as pd

LAG_DAYS = (1, 7, 14, 28)
ROLL_WINDOWS = (7, 14, 28)
WARMUP_DAYS = 28

FEATURE_COLUMNS = (
    [f"lag_{d}" for d in LAG_DAYS]
    + [f"roll_mean_{w}" for w in ROLL_WINDOWS]
    + [f"roll_std_{w}" for w in ROLL_WINDOWS]
    + [
        "dow",
        "dom",
        "week_of_year",
        "promo_flag",
        "event_flag",
        "price_paise",
        "price_vs_median",
    ]
)


def _ensure_series(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("sale_date").copy()
    out["sale_date"] = pd.to_datetime(out["sale_date"])
    out["units"] = out["units"].astype(float)
    return out


def build_product_features(product_df: pd.DataFrame) -> pd.DataFrame:
    """Per-product daily features; rolling stats use shift(1) on units."""
    df = _ensure_series(product_df)
    y = df["units"]
    for lag in LAG_DAYS:
        df[f"lag_{lag}"] = y.shift(lag)
    shifted = y.shift(1)
    for w in ROLL_WINDOWS:
        df[f"roll_mean_{w}"] = shifted.rolling(w, min_periods=1).mean()
        df[f"roll_std_{w}"] = shifted.rolling(w, min_periods=1).std().fillna(0.0)

    df["dow"] = df["sale_date"].dt.dayofweek
    df["dom"] = df["sale_date"].dt.day
    df["week_of_year"] = df["sale_date"].dt.isocalendar().week.astype(int)
    df["promo_flag"] = df.get("promo_flag", 0).fillna(0).astype(float)
    df["event_flag"] = df.get("event_flag", 0).fillna(0).astype(float)
    df["price_paise"] = df.get("selling_price_paise", 0).fillna(0).astype(float)
    med = df["price_paise"].median() or 1.0
    df["price_vs_median"] = df["price_paise"] / med
    df["target_units"] = y
    return df


def build_panel_features(sales: pd.DataFrame) -> pd.DataFrame:
    """Stacked panel with product_id and feature columns."""
    parts = []
    for pid, grp in sales.groupby("product_id"):
        feat = build_product_features(grp)
        feat["product_id"] = int(pid)
        parts.append(feat)
    if not parts:
        return pd.DataFrame(columns=["product_id", "sale_date", "target_units", *FEATURE_COLUMNS])
    out = pd.concat(parts, ignore_index=True)
    out = out.dropna(subset=[c for c in FEATURE_COLUMNS if c.startswith("lag_")])
    return out


def feature_matrix(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    cols = [c for c in FEATURE_COLUMNS if c in df.columns]
    x = df[cols].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).values
    y = df["target_units"].astype(float).values
    return x, y


def load_sales_dataframe(conn) -> pd.DataFrame:
    import sqlite3

    rows = conn.execute(
        """
        SELECT product_id, sale_date, units, selling_price_paise, promo_flag, event_flag
        FROM sales ORDER BY product_id, sale_date
        """
    ).fetchall()
    if not rows:
        return pd.DataFrame(
            columns=[
                "product_id",
                "sale_date",
                "units",
                "selling_price_paise",
                "promo_flag",
                "event_flag",
            ]
        )
    return pd.DataFrame([dict(r) for r in rows])
