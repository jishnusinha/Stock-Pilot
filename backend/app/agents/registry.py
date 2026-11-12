"""Agent registry and load helpers."""

from __future__ import annotations

from typing import Type

from app.agents.base import BaseAgent, TrainContext
from app.agents.calendar_effect import CalendarEffectAgent
from app.agents.demand import DemandAgent
from app.agents.demand_interval import DemandIntervalAgent
from app.agents.excess_risk import ExcessRiskAgent
from app.agents.intermittence import IntermittenceAgent
from app.agents.price_response import PriceResponseAgent
from app.agents.product_similarity import ProductSimilarityAgent
from app.agents.sales_anomaly import SalesAnomalyAgent
from app.agents.stockout_risk import StockoutRiskAgent
from app.agents.supplier_eta import SupplierEtaAgent

AGENT_CLASSES: dict[str, Type[BaseAgent]] = {
    "demand": DemandAgent,
    "demand_interval": DemandIntervalAgent,
    "intermittence": IntermittenceAgent,
    "price_response": PriceResponseAgent,
    "calendar_effect": CalendarEffectAgent,
    "sales_anomaly": SalesAnomalyAgent,
    "product_similarity": ProductSimilarityAgent,
    "supplier_eta": SupplierEtaAgent,
    "stockout_risk": StockoutRiskAgent,
    "excess_risk": ExcessRiskAgent,
}

AGENT_ORDER = list(AGENT_CLASSES.keys())


def get_agent(name: str) -> BaseAgent:
    cls = AGENT_CLASSES.get(name)
    if not cls:
        raise KeyError(f"Unknown agent: {name}")
    return cls()


def train_agent(name: str, ctx: TrainContext):
    return get_agent(name).train(ctx)


def train_all(ctx: TrainContext) -> list:
    results = []
    for name in AGENT_ORDER:
        agent = get_agent(name)
        ctx_agent = TrainContext(
            conn=ctx.conn,
            fast=ctx.fast,
            threads=ctx.threads,
            provenance=agent.provenance if hasattr(agent, "provenance") else ctx.provenance,
        )
        results.append(agent.train(ctx_agent))
    return results


def load_agent(name: str, version: str | None = None) -> BaseAgent:
    agent = get_agent(name)
    agent.load(version)
    return agent
