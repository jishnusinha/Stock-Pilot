"""Forecast and classification metrics with safe N/A handling."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def _is_valid(x: float | None) -> bool:
    if x is None:
        return False
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    if len(y_true) == 0:
        return None
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    if len(y_true) == 0:
        return None
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def wape(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    denom = float(np.sum(np.abs(y_true)))
    if denom <= 0:
        return None
    return float(np.sum(np.abs(y_true - y_pred)) / denom)


def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, alpha: float) -> float | None:
    if len(y_true) == 0:
        return None
    err = y_true - y_pred
    loss = np.where(err >= 0, alpha * err, (alpha - 1) * err)
    return float(np.mean(loss))


def interval_coverage(
    y_true: np.ndarray, low: np.ndarray, high: np.ndarray
) -> float | None:
    if len(y_true) == 0:
        return None
    inside = (y_true >= low) & (y_true <= high)
    return float(np.mean(inside))


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float | None:
    if len(y_true) == 0:
        return None
    y_true = y_true.astype(float)
    y_prob = np.clip(y_prob.astype(float), 0.0, 1.0)
    return float(np.mean((y_prob - y_true) ** 2))


def reconcile_quantiles(p10: float, p50: float, p90: float) -> tuple[float, float, float]:
    """Enforce p10 <= p50 <= p90."""
    a, b, c = float(p10), float(p50), float(p90)
    b = max(a, min(b, c))
    a = min(a, b)
    c = max(c, b)
    return a, b, c


def metric_display(name: str, value: float | None) -> str:
    if not _is_valid(value):
        return "N/A"
    if name in {"wape", "coverage", "brier", "stockout_risk", "excess_risk"}:
        return f"{value:.4f}"
    return f"{value:.3f}"


def pack_metrics(**kwargs: Any) -> dict[str, float | None]:
    return {k: (v if _is_valid(v) else None) for k, v in kwargs.items()}
