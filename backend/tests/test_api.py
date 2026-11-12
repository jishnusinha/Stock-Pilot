"""API contract tests with isolated temp SQLite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.migrations import migrate
from app.main import app
from app.services.seed import seed_demo


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    models = tmp_path / "models"
    monkeypatch.setattr(settings, "db_path", db)
    monkeypatch.setattr(settings, "model_dir", models)
    monkeypatch.setattr(settings, "eval_dir", tmp_path / "eval")
    settings.ensure_dirs()
    from app.db.connection import connect

    conn = connect(db)
    migrate(conn)
    seed_demo(conn, products=8, days=60, seed=7)
    conn.close()
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["db_ready"] is True
    assert "demo_date" in body
    assert "path" not in body  # no local path leak


def test_dashboard_and_products(client):
    d = client.get("/api/dashboard")
    assert d.status_code == 200
    assert "kpis" in d.json()
    p = client.get("/api/products", params={"page": 1, "page_size": 5})
    assert p.status_code == 200
    data = p.json()
    assert data["total"] >= 8
    assert len(data["items"]) <= 5


def test_product_adjust_and_filter(client):
    items = client.get("/api/products").json()["items"]
    pid = items[0]["id"]
    before = client.get(f"/api/products/{pid}").json()["current_stock"]
    bad = client.post(f"/api/products/{pid}/adjust-stock", json={"delta": -(before + 5), "reason": "x"})
    assert bad.status_code == 400
    ok = client.post(f"/api/products/{pid}/adjust-stock", json={"delta": 2, "reason": "test"})
    assert ok.status_code == 200
    assert ok.json()["current_stock"] == before + 2
    cat = items[0].get("category")
    if cat:
        f = client.get("/api/products", params={"category": cat})
        assert f.status_code == 200
        assert all(i["category"] == cat for i in f.json()["items"])


def test_simulate_and_scenario(client):
    pid = client.get("/api/products").json()["items"][0]["id"]
    detail = client.get(f"/api/products/{pid}").json()
    price = detail["unit_price_paise"]
    s0 = client.post(
        "/api/simulate",
        json={
            "product_id": pid,
            "reorder_qty": 0,
            "proposed_price_paise": price,
            "lead_time_days": 5,
            "budget_paise": 500000,
        },
    )
    assert s0.status_code == 200
    s1 = client.post(
        "/api/simulate",
        json={
            "product_id": pid,
            "reorder_qty": max(detail.get("pack_size") or 12, 12),
            "proposed_price_paise": price,
            "lead_time_days": 5,
            "budget_paise": 500000,
        },
    )
    assert s1.status_code == 200
    # Higher order should not lower ending inventory on deterministic path (arrival day)
    end0 = s0.json()["proposed_series"][-1]["inventory"]
    end1 = s1.json()["proposed_series"][-1]["inventory"]
    assert end1 >= end0
    sc = client.post(
        "/api/scenarios",
        json={"name": "t1", "product_id": pid, "inputs": s1.json(), "results": s1.json()},
    )
    assert sc.status_code == 200


def test_reorder_lifecycle(client):
    pid = client.get("/api/products").json()["items"][0]["id"]
    detail = client.get(f"/api/products/{pid}").json()
    from app.db.connection import connect
    from app.db import repositories as repo

    conn = connect(settings.db_path)
    rid = repo.create_reorder(
        conn, pid, qty=12, unit_cost_paise=int(detail["unit_cost_paise"] or 100)
    )
    conn.commit()
    conn.close()
    stock0 = detail["current_stock"]
    a = client.post(f"/api/reorders/{rid}/approve")
    assert a.status_code == 200
    assert a.json()["status"] == "approved"
    mid = client.get(f"/api/products/{pid}").json()["current_stock"]
    assert mid == stock0  # approve does not add stock
    r = client.post(f"/api/reorders/{rid}/receive")
    assert r.status_code == 200
    assert r.json()["status"] == "received"
    after = client.get(f"/api/products/{pid}").json()["current_stock"]
    assert after == stock0 + 12
    # second receive should fail
    again = client.post(f"/api/reorders/{rid}/receive")
    assert again.status_code == 409


def test_missing_product_and_trace(client):
    assert client.get("/api/products/999999").status_code == 404
    assert client.get("/api/agent-runs/no-such-trace").status_code == 404


def test_agents_and_performance(client):
    a = client.get("/api/agents")
    assert a.status_code == 200
    assert len(a.json()) == 10
    p = client.get("/api/performance")
    assert p.status_code == 200
    assert "kpis" in p.json()
