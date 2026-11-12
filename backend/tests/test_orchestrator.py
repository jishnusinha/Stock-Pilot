from app.agents.base import TrainContext
from app.agents.registry import train_all
from app.services.seed import seed_demo
from app.services.orchestrator import run_decision


def test_run_decision_minimal(tmp_db):
    seed_demo(tmp_db, products=12, days=100, seed=7)
    train_all(TrainContext(conn=tmp_db, fast=True, threads=1))
    tmp_db.commit()
    out = run_decision(tmp_db, 1, persist_trace=True)
    assert "suggested_qty" in out
    assert "trace_id" in out
    assert out["suggested_qty"] >= 0
