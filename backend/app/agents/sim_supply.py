"""Simulated inventory trajectories for risk classifiers.

Decision-time features (X) never include future-only outcomes.
Labels (y) are derived solely from the simulated future path.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.agents.base import PROVENANCE_SIMULATED

# Versioned shared schema — fit and predict MUST use identical columns/order.
DECISION_TIME_FEATURES: tuple[str, ...] = (
    "stock_on_hand",
    "reorder_point",
    "pack_size",
    "daily_demand",
    "lead_days",
    "order_qty",
    "shelf_life_days",
    "demand_p90",
)

FUTURE_ONLY_OUTCOMES: tuple[str, ...] = (
    "stockout_days",
    "unmet_demand_units",
    "excess_peak",
    "spoil_risk",
)

FEATURE_SCHEMA_VERSION = "decision_time_v1"


def decision_time_feature_vector(
    *,
    stock: int | float,
    reorder_point: int | float,
    pack_size: int | float,
    daily_demand: float,
    lead_days: int | float,
    order_qty: int | float,
    shelf_life_days: int | float | None,
    demand_p90: float | None = None,
) -> np.ndarray:
    """Build a 1-D feature vector in DECISION_TIME_FEATURES order."""
    shelf = float(shelf_life_days) if shelf_life_days is not None else 365.0
    p90 = float(demand_p90) if demand_p90 is not None else float(daily_demand) * 1.25
    values = {
        "stock_on_hand": float(stock),
        "reorder_point": float(reorder_point),
        "pack_size": float(pack_size),
        "daily_demand": float(daily_demand),
        "lead_days": float(lead_days),
        "order_qty": float(order_qty),
        "shelf_life_days": shelf,
        "demand_p90": p90,
    }
    return np.array([values[c] for c in DECISION_TIME_FEATURES], dtype=float)


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
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Return X (decision-time only), y_stockout, y_excess, and metadata."""
    horizon = 28
    rows_x: list[np.ndarray] = []
    y_so: list[int] = []
    y_ex: list[int] = []
    outcome_stockout_days: list[float] = []
    outcome_excess_peak: list[float] = []
    outcome_unmet: list[float] = []

    for _ in range(n):
        d = max(0.1, daily_demand * float(rng.uniform(0.6, 1.4)))
        demand_p90 = d * float(rng.uniform(1.1, 1.4))
        inv = float(stock)
        stockout_days = 0
        unmet = 0.0
        excess_peak = 0.0
        # Candidate order quantity known at decision time
        order_qty = max(pack_size, int(reorder_point * float(rng.uniform(0.8, 1.5))))
        order_arrival = lead_days + int(rng.integers(0, 3))

        # Decision-time features ONLY (before simulating the path)
        feat = decision_time_feature_vector(
            stock=stock,
            reorder_point=reorder_point,
            pack_size=pack_size,
            daily_demand=d,
            lead_days=lead_days,
            order_qty=order_qty,
            shelf_life_days=shelf_life,
            demand_p90=demand_p90,
        )

        for day in range(horizon):
            day_demand = d * float(rng.uniform(0.8, 1.2))
            if inv >= day_demand:
                inv -= day_demand
            else:
                unmet += day_demand - inv
                stockout_days += 1
                inv = 0.0
            if day == order_arrival:
                inv += order_qty
            excess_peak = max(excess_peak, inv)

        spoil_risk = 0.0
        if shelf_life and shelf_life < 30:
            spoil_risk = excess_peak / max(1.0, reorder_point * 2)

        rows_x.append(feat)
        y_so.append(1 if stockout_days >= 3 else 0)
        y_ex.append(1 if excess_peak > reorder_point * 2.5 else 0)
        outcome_stockout_days.append(float(stockout_days))
        outcome_excess_peak.append(float(excess_peak))
        outcome_unmet.append(float(unmet))
        _ = spoil_risk  # outcome only; never packed into X

    meta: dict[str, Any] = {
        "feature_names": list(DECISION_TIME_FEATURES),
        "schema_version": FEATURE_SCHEMA_VERSION,
        "provenance": PROVENANCE_SIMULATED,
        "outcomes": {
            "stockout_days": np.array(outcome_stockout_days, dtype=float),
            "excess_peak": np.array(outcome_excess_peak, dtype=float),
            "unmet_demand_units": np.array(outcome_unmet, dtype=float),
        },
    }
    return (
        np.vstack(rows_x),
        np.array(y_so, dtype=int),
        np.array(y_ex, dtype=int),
        meta,
    )
