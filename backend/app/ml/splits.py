"""Temporal train / validation / holdout splits."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.ml.features import WARMUP_DAYS

HOLDOUT_DAYS = 28
VAL_DAYS = 28


@dataclass(frozen=True)
class TemporalSplit:
    train: pd.DataFrame
    val: pd.DataFrame
    holdout: pd.DataFrame
    train_start: str | None
    train_end: str | None
    val_start: str | None
    val_end: str | None
    holdout_start: str | None
    holdout_end: str | None


def split_panel(features: pd.DataFrame) -> TemporalSplit:
    """Global calendar split on sale_date across the panel."""
    if features.empty:
        empty = features.copy()
        return TemporalSplit(empty, empty, empty, None, None, None, None, None, None)

    df = features.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    dates = sorted(df["sale_date"].unique())
    if len(dates) <= HOLDOUT_DAYS + VAL_DAYS + WARMUP_DAYS:
        # tiny dataset: all train, empty val/holdout
        tr = df[df["sale_date"] >= dates[min(WARMUP_DAYS, len(dates) - 1)]]
        return TemporalSplit(tr, df.iloc[0:0], df.iloc[0:0], None, None, None, None, None, None)

    holdout_dates = dates[-HOLDOUT_DAYS:]
    val_dates = dates[-(HOLDOUT_DAYS + VAL_DAYS) : -HOLDOUT_DAYS]
    train_dates = dates[: -(HOLDOUT_DAYS + VAL_DAYS)]

    holdout = df[df["sale_date"].isin(holdout_dates)]
    val = df[df["sale_date"].isin(val_dates)]
    warmup_cut = train_dates[WARMUP_DAYS] if len(train_dates) > WARMUP_DAYS else train_dates[-1]
    train = df[(df["sale_date"].isin(train_dates)) & (df["sale_date"] >= warmup_cut)]

    def _s(dates_list):
        if not dates_list:
            return None, None
        return (
            pd.Timestamp(dates_list[0]).strftime("%Y-%m-%d"),
            pd.Timestamp(dates_list[-1]).strftime("%Y-%m-%d"),
        )

    ts, te = _s([d for d in train["sale_date"].unique()])
    vs, ve = _s([d for d in val["sale_date"].unique()])
    hs, he = _s([d for d in holdout["sale_date"].unique()])
    return TemporalSplit(train, val, holdout, ts, te, vs, ve, hs, he)


def split_name(split: str) -> str:
    return split.lower().strip()
