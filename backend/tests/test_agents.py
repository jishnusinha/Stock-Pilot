from app.agents.base import TrainContext
from app.agents.demand import DemandAgent
from app.services.seed import seed_demo


def test_demand_agent_train_fast(tmp_db):
    seed_demo(tmp_db, products=15, days=120, seed=1)
    agent = DemandAgent()
    res = agent.train(TrainContext(conn=tmp_db, fast=True, threads=1))
    assert res.status == "ok"
    pred = agent.predict(tmp_db, 1)
    assert pred.status == "ok"
    assert "p50_units" in pred.output
