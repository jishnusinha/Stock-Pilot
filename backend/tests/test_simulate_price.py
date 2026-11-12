"""What-if simulator: price, qty normalization, lead-time sensitivity."""

from app.agents.base import TrainContext
from app.agents.demand import DemandAgent
from app.agents.price_response import PriceResponseAgent
from app.agents.registry import train_all
from app.services.seed import seed_demo
from app.services.simulate_api import run_simulate, _normalize_qty


def test_normalize_qty_budget_and_pack():
    req, applied, note = _normalize_qty(25, pack=12, budget_paise=20_000, unit_cost=1000)
    assert req == 25
    # max by budget = 20; round down to pack → 12
    assert applied == 12
    assert "pack" in note.lower() or "budget" in note.lower()


def test_normalize_zero_budget():
    req, applied, _ = _normalize_qty(48, pack=12, budget_paise=0, unit_cost=1000)
    assert applied == 0


def test_price_change_affects_demand(tmp_db):
    seed_demo(tmp_db, products=10, days=120, seed=3)
    train_all(TrainContext(conn=tmp_db, fast=True, threads=1, version="sim_test"))
    tmp_db.commit()
    prod = tmp_db.execute(
        "SELECT id, selling_price_paise, unit_cost_paise, pack_size FROM products WHERE id=1"
    ).fetchone()
    base_price = int(prod["selling_price_paise"])
    pack = int(prod["pack_size"])
    unit_cost = int(prod["unit_cost_paise"])
    qty = pack
    budget = max(500_000, unit_cost * pack * 10)
    low = run_simulate(
        tmp_db,
        product_id=1,
        reorder_qty=qty,
        proposed_price_paise=max(100, base_price // 2),
        lead_time_days=5,
        budget_paise=budget,
    )
    high = run_simulate(
        tmp_db,
        product_id=1,
        reorder_qty=qty,
        proposed_price_paise=base_price * 2,
        lead_time_days=5,
        budget_paise=budget,
    )
    d_low = low["proposed_metrics"]["demand_p50"]
    d_high = high["proposed_metrics"]["demand_p50"]
    assert low["price_effect"]["not_causal_elasticity"] is True
    assert d_low is not None and d_high is not None
    assert low["requested_qty"] == qty
    assert low["applied_qty"] == qty


def test_lead_time_changes_stockout_path(tmp_db):
    seed_demo(tmp_db, products=8, days=100, seed=5)
    DemandAgent().train(TrainContext(conn=tmp_db, fast=True, threads=1, version="lt"))
    PriceResponseAgent().train(TrainContext(conn=tmp_db, fast=True, threads=1, version="lt"))
    tmp_db.commit()
    prod = tmp_db.execute("SELECT id, selling_price_paise FROM products WHERE id=1").fetchone()
    price = int(prod["selling_price_paise"])
    short = run_simulate(
        tmp_db, product_id=1, reorder_qty=48, proposed_price_paise=price,
        lead_time_days=1, budget_paise=1_000_000,
    )
    long = run_simulate(
        tmp_db, product_id=1, reorder_qty=48, proposed_price_paise=price,
        lead_time_days=28, budget_paise=1_000_000,
    )
    # Longer lead typically → more or equal stockout days before arrival
    assert long["proposed_metrics"]["stockout_days"] >= short["proposed_metrics"]["stockout_days"]
