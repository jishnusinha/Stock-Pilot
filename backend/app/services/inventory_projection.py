"""Deterministic inventory projection paths from demand series + receipts.

Uses the same conservation rules as scenarios.simulate_stock_path, but accepts
per-day demand and dated receipt events. Never invents arrivals without dates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class ReceiptEvent:
    day_index: int  # 1-based day within the horizon
    qty: float
    source: str  # approved_reorder | recommended | scenario
    date_role: str = "predicted"  # predicted | actual_planned


@dataclass
class ProjectionDay:
    day: int
    date: str
    predicted_demand: float
    fulfilled_units: float
    closing_stock: float
    closing_value_paise: int
    receipts: float
    unmet_demand: float
    cumulative_unmet: float


@dataclass
class ProjectionResult:
    days: list[ProjectionDay]
    ending_stock: float
    ending_value_paise: int
    unmet_demand_units: float
    stockout_days: int
    min_stock: float
    total_receipts: float
    mode: str
    model_version: str | None = None
    provenance: str = "SYNTHETIC_DEMO"
    notes: list[str] = field(default_factory=list)


def project_inventory_path(
    *,
    opening_stock: float,
    unit_cost_paise: int,
    as_of_date: str,
    daily_demand: list[float],
    receipts: list[ReceiptEvent] | None = None,
    mode: str = "no_reorder",
    model_version: str | None = None,
    provenance: str = "SYNTHETIC_DEMO",
) -> ProjectionResult:
    """Project closing stock for each day. Stock never goes below zero."""
    if not daily_demand:
        raise ValueError("daily_demand must not be empty")
    stock = max(0.0, float(opening_stock))
    cost = max(0, int(unit_cost_paise))
    origin = datetime.fromisoformat(as_of_date).date()
    receipt_map: dict[int, list[ReceiptEvent]] = {}
    for event in receipts or []:
        receipt_map.setdefault(int(event.day_index), []).append(event)

    days: list[ProjectionDay] = []
    unmet_total = 0.0
    stockout_days = 0
    min_stock = stock
    total_receipts = 0.0

    for day_idx, demand_raw in enumerate(daily_demand, start=1):
        demand = max(0.0, float(demand_raw))
        day_receipts = 0.0
        for event in receipt_map.get(day_idx, []):
            day_receipts += max(0.0, float(event.qty))
        total_receipts += day_receipts
        available = stock + day_receipts
        if available >= demand:
            fulfilled = demand
            stock = available - demand
        else:
            fulfilled = available
            unmet = demand - available
            unmet_total += unmet
            stockout_days += 1
            stock = 0.0
        min_stock = min(min_stock, stock)
        target = (origin + timedelta(days=day_idx)).isoformat()
        days.append(
            ProjectionDay(
                day=day_idx,
                date=target,
                predicted_demand=demand,
                fulfilled_units=fulfilled,
                closing_stock=stock,
                closing_value_paise=int(round(stock * cost)),
                receipts=day_receipts,
                unmet_demand=max(0.0, demand - fulfilled),
                cumulative_unmet=unmet_total,
            )
        )

    return ProjectionResult(
        days=days,
        ending_stock=stock,
        ending_value_paise=int(round(stock * cost)),
        unmet_demand_units=unmet_total,
        stockout_days=stockout_days,
        min_stock=min_stock,
        total_receipts=total_receipts,
        mode=mode,
        model_version=model_version,
        provenance=provenance,
    )


def day_index_for_date(as_of_date: str, arrival_date: str, horizon_days: int) -> int | None:
    """Map an ISO arrival date to a 1-based projection day, or None if outside horizon."""
    origin = datetime.fromisoformat(as_of_date).date()
    arrival = datetime.fromisoformat(str(arrival_date)[:10]).date()
    delta = (arrival - origin).days
    if delta < 1 or delta > horizon_days:
        return None
    return delta
