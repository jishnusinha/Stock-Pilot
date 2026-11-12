"""28-day inventory path simulation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScenarioInput:
    stock_on_hand: int
    daily_demand_p50: float
    order_qty: int
    lead_days: int
    pack_size: int
    horizon_days: int = 28


@dataclass
class ScenarioPath:
    days: list[dict]
    stockout_days: int
    min_stock: int
    ending_stock: int
    unmet_demand_units: float = 0.0


def simulate_stock_path(inp: ScenarioInput) -> ScenarioPath:
    stock = float(inp.stock_on_hand)
    arrival = max(0, int(inp.lead_days))
    stockout = 0
    unmet = 0.0
    min_s = stock
    demand = max(0.0, float(inp.daily_demand_p50))
    days = []
    for d in range(1, inp.horizon_days + 1):
        # Arrival at start of day (before demand) when lead_days matches day index
        if d == arrival:
            stock += float(inp.order_qty)
        if stock >= demand:
            stock -= demand
        else:
            unmet += demand - stock
            stockout += 1
            stock = 0.0
        min_s = min(min_s, stock)
        days.append({"day": d, "stock": int(round(stock)), "unmet": unmet})
    return ScenarioPath(
        days=days,
        stockout_days=stockout,
        min_stock=int(round(min_s)),
        ending_stock=int(round(stock)),
        unmet_demand_units=float(unmet),
    )
