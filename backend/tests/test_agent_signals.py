"""Upstream agent signals must change demand / decisions."""

from app.agents.base import TrainContext
from app.agents.demand import DemandAgent
from app.agents.registry import train_all
from app.services.orchestrator import run_decision
from app.services.seed import seed_demo


def test_price_delta_changes_demand_predict(tmp_db):
    seed_demo(tmp_db, products=10, days=120, seed=2)
    agent = DemandAgent()
    agent.train(TrainContext(conn=tmp_db, fast=True, threads=1, version="sig"))
    base = agent.predict(tmp_db, 1).output["p50_units"]
    boosted = agent.predict(tmp_db, 1, price_units_delta=5.0).output["p50_units"]
    assert boosted == base + 5.0 or abs(boosted - (base + 5.0)) < 1e-6


def test_decision_exposes_signal_flow(tmp_db):
    seed_demo(tmp_db, products=12, days=100, seed=4)
    train_all(TrainContext(conn=tmp_db, fast=True, threads=1, version="sig2"))
    tmp_db.commit()
    out = run_decision(tmp_db, 1, persist_trace=False)
    assert "signal_flow" in out
    assert "demand_p50" in out["signal_flow"]
    assert out["signal_flow"]["optimizer_used_candidate_risks"] in (True, False)
