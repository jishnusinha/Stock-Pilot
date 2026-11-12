"""Deterministic reorder quantity optimizer (pack-size multiples)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.scenarios import ScenarioInput, simulate_stock_path


@dataclass
class OptimizeInput:
    stock_on_hand: int
    daily_demand: float
    unit_cost_paise: int
    pack_size: int
    lead_days: int
    stockout_risk: float
    excess_risk: float
    budget_paise: int
    shelf_life_days: int | None = None


@dataclass
class OptimizeResult:
    suggested_qty: int
    estimated_cost_paise: int
    total_cost_score: float
    stock_path: list[dict]
    rationale: list[str]


def optimize_reorder(inp: OptimizeInput) -> OptimizeResult:
    pack = max(1, inp.pack_size)
    max_packs = max(1, inp.budget_paise // max(1, inp.unit_cost_paise * pack))
    best = None
    holding_rate = 0.02
    lost_sales = 8.0
    spoil = 0.05 if inp.shelf_life_days and inp.shelf_life_days < 21 else 0.01

    for n_pack in range(0, max_packs + 1):
        qty = n_pack * pack
        path = simulate_stock_path(
            ScenarioInput(
                stock_on_hand=inp.stock_on_hand,
                daily_demand_p50=inp.daily_demand,
                order_qty=qty,
                lead_days=inp.lead_days,
                pack_size=pack,
            )
        )
        holding = path.ending_stock * inp.unit_cost_paise * holding_rate
        lost = path.stockout_days * inp.daily_demand * lost_sales * (inp.unit_cost_paise * 0.3)
        spoil_cost = max(0, path.ending_stock - inp.daily_demand * 14) * inp.unit_cost_paise * spoil
        risk_pen = (inp.stockout_risk * lost_sales + inp.excess_risk * spoil) * 1000
        score = holding + lost + spoil_cost + risk_pen
        cost = qty * inp.unit_cost_paise
        if best is None or score < best[0]:
            best = (score, qty, cost, path)

    assert best is not None
    score, qty, cost, path = best
    rationale = [
        f"Daily demand ~{inp.daily_demand:.1f} units; lead time {inp.lead_days}d.",
        f"Pack size {pack}; order in multiples to respect supplier case packs.",
        f"Projected stockout days: {path.stockout_days} over 28d horizon.",
        f"Stockout risk {inp.stockout_risk:.2f}, excess risk {inp.excess_risk:.2f}.",
    ]
    return OptimizeResult(
        suggested_qty=int(qty),
        estimated_cost_paise=int(cost),
        total_cost_score=float(score),
        stock_path=path.days,
        rationale=rationale,
    )
