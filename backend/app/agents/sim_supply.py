"""Simulated inventory trajectories for risk classifiers."""

from __future__ import annotations

import numpy as np

from app.agents.base import PROVENANCE_SIMULATED


def simulate_scenarios(
    rng: np.random.Generator,
    n: int,
    *,
    stock: int,
    reorder_point: int,
    pack_size: int,
    daily_demand: float,
    lead_days: int,
    shelf_life: int | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return X, y_stockout, y_excess for n scenarios."""
    horizon = 28
    rows_x, y_so, y_ex = [], [], []
    for _ in range(n):
        d = max(0.1, daily_demand * rng.uniform(0.6, 1.4))
        inv = float(stock)
        stockout_days = 0
        excess_peak = 0.0
        order_qty = max(pack_size, int(reorder_point * rng.uniform(0.8, 1.5)))
        order_arrival = lead_days + int(rng.integers(0, 3))
        for day in range(horizon):
            inv -= d * rng.uniform(0.8, 1.2)
            if day == order_arrival:
                inv += order_qty
            if inv < 0:
                stockout_days += 1
                inv = 0
            excess_peak = max(excess_peak, inv)
        spoil_risk = 0.0
        if shelf_life and shelf_life < 30:
            spoil_risk = excess_peak / max(1.0, reorder_point * 2)
        feat = [
            stock,
            reorder_point,
            pack_size,
            d,
            lead_days,
            order_qty,
            stockout_days,
            excess_peak,
            spoil_risk,
        ]
        rows_x.append(feat)
        y_so.append(1 if stockout_days >= 3 else 0)
        y_ex.append(1 if excess_peak > reorder_point * 2.5 else 0)
    return np.array(rows_x, dtype=float), np.array(y_so), np.array(y_ex)
