"""Deterministic reorder quantity optimizer (pack-size multiples).

Hard constraints:
- qty is 0 or a nonnegative pack multiple
- purchase cost must not exceed budget (budget=0 → only qty=0)
- never force an unaffordable pack via max(1, ...)

Objective uses candidate-specific inventory path costs (holding, shortage,
spoilage). Optional risk_fn(qty) may add a candidate-dependent penalty; a
constant risk value does not change argmin across candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

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
    # Optional: callable(qty) -> (stockout_risk, excess_risk) for candidate-specific risks
    risk_fn: Callable[[int], tuple[float, float]] | None = None
    shortage_penalty_per_unit: float = 0.3  # fraction of unit cost as lost margin proxy
    holding_rate_28d: float = 0.02
    seed: int = 42


@dataclass
class OptimizeResult:
    suggested_qty: int
    estimated_cost_paise: int
    total_cost_score: float
    stock_path: list[dict]
    rationale: list[str]
    unmet_demand_units: float = 0.0
    feasible: bool = True
    objective_breakdown: dict | None = None


def _max_affordable_packs(budget_paise: int, unit_cost_paise: int, pack: int) -> int:
    """Largest n such that n*pack*unit_cost <= budget. May be 0."""
    if budget_paise <= 0 or unit_cost_paise <= 0 or pack <= 0:
        return 0
    pack_cost = unit_cost_paise * pack
    if pack_cost <= 0:
        return 0
    return budget_paise // pack_cost


def optimize_reorder(inp: OptimizeInput) -> OptimizeResult:
    pack = max(1, int(inp.pack_size))
    max_packs = _max_affordable_packs(inp.budget_paise, inp.unit_cost_paise, pack)
    # Candidate set: 0 .. max_packs (inclusive). Never force a pack when unaffordable.
    candidates = list(range(0, max_packs + 1))

    holding_rate = float(inp.holding_rate_28d)
    lost_margin = float(inp.shortage_penalty_per_unit)
    spoil = 0.05 if inp.shelf_life_days and inp.shelf_life_days < 21 else 0.01

    best: tuple | None = None
    demand = max(0.0, float(inp.daily_demand))

    for n_pack in candidates:
        qty = n_pack * pack
        path = simulate_stock_path(
            ScenarioInput(
                stock_on_hand=inp.stock_on_hand,
                daily_demand_p50=demand,
                order_qty=qty,
                lead_days=inp.lead_days,
                pack_size=pack,
            )
        )
        unmet = float(getattr(path, "unmet_demand_units", path.stockout_days * demand))
        holding = path.ending_stock * inp.unit_cost_paise * holding_rate
        shortage = unmet * lost_margin * inp.unit_cost_paise
        spoil_cost = (
            max(0.0, path.ending_stock - demand * 14) * inp.unit_cost_paise * spoil
        )

        if inp.risk_fn is not None:
            so_r, ex_r = inp.risk_fn(qty)
            # Candidate-dependent: scale by path-relevant magnitudes so it can change argmin
            risk_pen = so_r * shortage * 0.25 + ex_r * spoil_cost * 0.25
        else:
            # Path-only objective — constant risks must not dominate or flatten ranking
            so_r, ex_r = inp.stockout_risk, inp.excess_risk
            risk_pen = 0.0

        score = holding + shortage + spoil_cost + risk_pen
        cost = qty * inp.unit_cost_paise
        breakdown = {
            "holding_paise": holding,
            "shortage_paise": shortage,
            "spoil_paise": spoil_cost,
            "risk_penalty": risk_pen,
            "stockout_risk": so_r,
            "excess_risk": ex_r,
            "unmet_demand_units": unmet,
        }
        if best is None or score < best[0] - 1e-9 or (
            abs(score - best[0]) <= 1e-9 and qty < best[1]
        ):
            best = (score, qty, cost, path, breakdown, unmet)

    assert best is not None
    score, qty, cost, path, breakdown, unmet = best
    rationale = [
        f"Daily demand ~{demand:.1f} units; lead time {inp.lead_days}d.",
        f"Pack size {pack}; candidates are 0..{max_packs} packs within budget {inp.budget_paise} paise.",
        f"Selected {qty} units (purchase {cost} paise) minimizing holding+shortage+spoil.",
        f"Projected unmet demand ≈{unmet:.1f} units; stockout days {path.stockout_days}/28.",
    ]
    if max_packs == 0 and inp.budget_paise < pack * max(1, inp.unit_cost_paise):
        rationale.append("Budget cannot afford one pack — only zero-quantity is feasible.")

    return OptimizeResult(
        suggested_qty=int(qty),
        estimated_cost_paise=int(cost),
        total_cost_score=float(score),
        stock_path=path.days,
        rationale=rationale,
        unmet_demand_units=float(unmet),
        feasible=True,
        objective_breakdown=breakdown,
    )
