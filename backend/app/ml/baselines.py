"""Simple forecasting baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd


def seasonal_naive_7(units: pd.Series) -> float:
    if len(units) < 7:
        return float(units.mean()) if len(units) else 0.0
    return float(units.iloc[-7:].mean())


def moving_average_28(units: pd.Series) -> float:
    if len(units) < 28:
        return float(units.mean()) if len(units) else 0.0
    return float(units.iloc[-28:].mean())


def predict_baseline(series: pd.Series, method: str) -> float:
    if method == "seasonal_naive_7":
        return seasonal_naive_7(series)
    if method == "moving_average_28":
        return moving_average_28(series)
    raise ValueError(method)
