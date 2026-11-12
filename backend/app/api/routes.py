"""All /api routes."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app import __version__
from app.agents.registry import AGENT_ORDER, get_agent
from app.api import schemas as S
from app.api.deps import get_db
from app.core.config import settings
from app.db import repositories as repo
from app.ml import artifacts
from app.api.analytics_routes import router as analytics_router
from app.services.dashboard import build_dashboard
from app.services.orchestrator import run_decision
from app.services.simulate_api import run_simulate

router = APIRouter(prefix="/api")
router.include_router(analytics_router)

# Edges match orchestrator signal flow (see docs/agent-dependency-contract.md).
# First-wave agents read sales/catalog features directly; there is no "data" model node.
DAG_EDGES = [
    {"from": "calendar_effect", "to": "demand"},
    {"from": "price_response", "to": "demand"},
    {"from": "intermittence", "to": "demand"},
    {"from": "sales_anomaly", "to": "demand"},
    {"from": "product_similarity", "to": "demand"},
    {"from": "demand", "to": "demand_interval"},
    {"from": "demand", "to": "stockout_risk"},
    {"from": "demand_interval", "to": "stockout_risk"},
    {"from": "supplier_eta", "to": "stockout_risk"},
    {"from": "demand", "to": "excess_risk"},
    {"from": "demand_interval", "to": "excess_risk"},
    {"from": "supplier_eta", "to": "excess_risk"},
    {"from": "demand", "to": "optimizer"},
    {"from": "supplier_eta", "to": "optimizer"},
    {"from": "stockout_risk", "to": "optimizer"},
    {"from": "excess_risk", "to": "optimizer"},
]


@router.get("/health", response_model=S.HealthResponse)
def health(conn: sqlite3.Connection = Depends(get_db)) -> Any:
    try:
        conn.execute("SELECT 1").fetchone()
        db_ready = True
    except Exception:
        db_ready = False
    arts = artifacts.list_agent_artifacts()
    n = len({a["agent_name"] for a in arts})
    return {
        "status": "ok" if db_ready else "degraded",
        "db_ready": db_ready,
        "models_available": n,
        "models_expected": 10,
        "demo_date": settings.demo_date,
        "version": __version__,
        "demo_mode": settings.demo_mode,
    }


@router.get("/dashboard", response_model=S.DashboardResponse)
def dashboard(conn: sqlite3.Connection = Depends(get_db)) -> Any:
    return build_dashboard(conn)


@router.post("/products", response_model=S.ProductDetail, status_code=201)
def create_product(body: S.ProductCreateRequest, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    try:
        p = repo.create_product(
            conn,
            {
                "sku": body.sku,
                "name": body.name,
                "category": body.category,
                "supplier_id": body.supplier_id,
                "unit_cost_paise": body.unit_cost_paise,
                "selling_price_paise": body.selling_price_paise,
                "stock_on_hand": body.stock_on_hand,
                "reorder_point": body.reorder_point if body.reorder_point is not None else body.pack_size,
                "pack_size": body.pack_size,
                "shelf_life_days": body.shelf_life_days,
            },
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return product_detail(int(p["id"]), conn)


@router.patch("/products/{product_id}", response_model=S.ProductDetail)
def patch_product(
    product_id: int,
    body: S.ProductUpdateRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(400, "No fields to update")
    try:
        repo.update_product(conn, product_id, payload)
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status, str(e)) from e
    return product_detail(product_id, conn)


@router.delete("/products/{product_id}")
def delete_product(product_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    try:
        repo.soft_delete_product(conn, product_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True, "id": product_id, "status": "deactivated"}


@router.get("/products", response_model=S.ProductsListResponse)
def products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=250),
    search: str | None = None,
    category: str | None = None,
    supplier_id: int | None = None,
    risk: str | None = None,
    stock_health: str | None = None,
    sort: str = "sku",
    direction: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    if direction is not None and direction not in ("asc", "desc"):
        raise HTTPException(400, "direction must be asc or desc")
    rows, total = repo.list_products(
        conn,
        search=search,
        category=category,
        supplier_id=supplier_id,
        risk=risk,
        stock_health=stock_health,
        sort=sort,
        direction=direction,
        page=page,
        page_size=page_size,
    )
    items = [
        {
            "id": r["id"],
            "sku": r["sku"],
            "name": r["name"],
            "category": r.get("category"),
            "supplier_name": r.get("supplier_name"),
            "supplier_id": r.get("supplier_id"),
            "current_stock": r["stock_on_hand"],
            "days_of_supply": r.get("days_of_supply"),
            "risk_level": r.get("risk_level"),
            "unit_price_paise": r.get("selling_price_paise"),
            "unit_cost_paise": r.get("unit_cost_paise"),
            "reorder_point": r.get("reorder_point"),
            "pack_size": r.get("pack_size"),
            "sell_through": r.get("sell_through"),
            "forecast_28d": r.get("forecast_28d"),
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/inventory/summary", response_model=S.InventorySummary)
def inventory_summary(conn: sqlite3.Connection = Depends(get_db)) -> Any:
    return repo.inventory_summary(conn)


@router.get("/products/export.csv")
def export_products_csv(
    search: str | None = None,
    category: str | None = None,
    supplier_id: int | None = None,
    risk: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> StreamingResponse:
    rows, _ = repo.list_products(
        conn,
        search=search,
        category=category,
        supplier_id=supplier_id,
        risk=risk,
        page=1,
        page_size=100,
    )
    # fetch more pages if needed (cap 2000)
    all_rows = list(rows)
    page = 2
    while len(rows) == 100 and len(all_rows) < 2000:
        rows, _ = repo.list_products(
            conn,
            search=search,
            category=category,
            supplier_id=supplier_id,
            risk=risk,
            page=page,
            page_size=100,
        )
        all_rows.extend(rows)
        page += 1

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["sku", "name", "category", "supplier", "stock_on_hand", "risk_level", "days_of_supply"]
    )
    for r in all_rows:
        writer.writerow(
            [
                r["sku"],
                r["name"],
                r.get("category"),
                r.get("supplier_name"),
                r["stock_on_hand"],
                r.get("risk_level"),
                r.get("days_of_supply"),
            ]
        )
    data = buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )


@router.get("/products/{product_id}", response_model=S.ProductDetail)
def product_detail(product_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    p = repo.get_product(conn, product_id)
    if not p or not int(p.get("is_active", 1)):
        raise HTTPException(404, "Product not found")
    as_of = settings.demo_date
    start = "2025-01-01"
    sales = repo.sales_range(conn, product_id, start, as_of)
    # last 60 days for chart
    sales = sales[-60:] if len(sales) > 60 else sales
    fc = repo.get_forecasts(conn, product_id, as_of)
    risk = conn.execute(
        "SELECT * FROM product_risk_cache WHERE product_id=?", (product_id,)
    ).fetchone()
    risk_d = dict(risk) if risk else {}
    moves = repo.recent_movements(conn, product_id)
    recs = [
        r for r in repo.get_open_recommendations(conn, limit=50) if r["product_id"] == product_id
    ]
    rec = None
    if recs:
        expl = {}
        try:
            expl = json.loads(recs[0].get("explanation_json") or "{}")
        except json.JSONDecodeError:
            pass
        rec = {
            "id": recs[0]["id"],
            "suggested_qty": recs[0]["suggested_qty"],
            "rationale": expl.get("summary"),
            "product_id": product_id,
            "trace_id": recs[0].get("trace_id"),
        }
    forecast_pts = [
        {
            "date": f["target_date"],
            "p10": f["p10_units"],
            "p50": f["p50_units"],
            "p90": f["p90_units"],
            "actual": None,
            "is_forecast": True,
        }
        for f in fc
    ]
    return {
        "id": p["id"],
        "sku": p["sku"],
        "name": p["name"],
        "category": p.get("category"),
        "description": f"{p['category']} · synthetic demo SKU",
        "current_stock": p["stock_on_hand"],
        "unit_price_paise": p["selling_price_paise"],
        "unit_cost_paise": p["unit_cost_paise"],
        "pack_size": p["pack_size"],
        "supplier": {
            "id": p["supplier_id"],
            "name": p.get("supplier_name") or "",
            "lead_time_days": p.get("base_lead_days"),
            "reliability_score": p.get("delivery_reliability"),
        },
        "risk_level": risk_d.get("risk_level"),
        "days_of_supply": risk_d.get("days_of_supply"),
        "forecast": forecast_pts,
        "sales_history": [{"date": s["sale_date"], "units": s["units"]} for s in sales],
        "movements": [
            {
                "id": m["id"],
                "created_at": m["created_at"],
                "delta": m["delta_units"],
                "reason": m["reason"],
                "balance_after": None,
            }
            for m in moves
        ],
        "reorder_recommendation": rec,
        "data_source": "SYNTHETIC_DEMO",
    }


@router.post("/products/{product_id}/adjust-stock", response_model=S.ProductDetail)
def adjust_stock(
    product_id: int,
    body: S.AdjustStockRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    try:
        repo.adjust_stock(conn, product_id, body.delta, body.reason)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return product_detail(product_id, conn)


@router.get("/suppliers", response_model=list[S.Supplier])
def suppliers(conn: sqlite3.Connection = Depends(get_db)) -> Any:
    rows = repo.list_suppliers(conn)
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "lead_time_days": r["base_lead_days"],
            "reliability_score": r["delivery_reliability"],
        }
        for r in rows
    ]


@router.get("/forecasts/{product_id}")
def forecasts(product_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    p = repo.get_product(conn, product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    series = repo.get_forecasts(conn, product_id)
    as_of = series[0]["as_of_date"] if series else settings.demo_date
    return {
        "as_of": as_of,
        "series": [
            {
                "date": s["target_date"],
                "p10": s["p10_units"],
                "p50": s["p50_units"],
                "p90": s["p90_units"],
            }
            for s in series
        ],
        "data_source": series[0]["provenance"] if series else "SYNTHETIC_DEMO",
        "interval_note": "Nominal p10–p90 ≈ 80% coverage",
    }


@router.post("/simulate", response_model=S.SimulateResponse)
def simulate(body: S.SimulateRequest, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    try:
        return run_simulate(
            conn,
            product_id=body.product_id,
            reorder_qty=body.reorder_qty,
            proposed_price_paise=body.proposed_price_paise,
            lead_time_days=body.lead_time_days,
            budget_paise=body.budget_paise,
            horizon_days=body.horizon_days or 28,
        )
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e).lower() else 400, str(e)) from e


@router.post("/scenarios", response_model=S.ScenarioSummary)
def save_scenario(body: S.SaveScenarioRequest, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    sid = repo.save_scenario(
        conn,
        body.product_id,
        body.inputs,
        body.results or {},
        provenance="SIMULATED_SUPPLY",
        name=body.name,
    )
    row = conn.execute("SELECT * FROM scenario_runs WHERE id=?", (sid,)).fetchone()
    return {
        "id": sid,
        "name": body.name,
        "product_id": body.product_id,
        "created_at": row["created_at"],
        "provenance": "SIMULATED_SUPPLY",
    }


@router.get("/scenarios", response_model=list[S.ScenarioSummary])
def list_scenarios(conn: sqlite3.Connection = Depends(get_db)) -> Any:
    rows = repo.list_scenarios(conn)
    return [
        {
            "id": r["id"],
            "name": r.get("name") or f"Scenario {r['id']}",
            "product_id": r["product_id"],
            "created_at": r["created_at"],
            "provenance": r.get("provenance"),
        }
        for r in rows
    ]


@router.get("/scenarios/{scenario_id}", response_model=S.ScenarioDetail)
def scenario_detail(scenario_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    row = repo.get_scenario(conn, scenario_id)
    if not row:
        raise HTTPException(404, "Scenario not found")
    return {
        "id": row["id"],
        "name": row.get("name") or f"Scenario {row['id']}",
        "product_id": row["product_id"],
        "created_at": row["created_at"],
        "provenance": row.get("provenance"),
        "inputs": row.get("inputs") or {},
        "results": row.get("results"),
    }


@router.post("/recommendations/{rec_id}/propose", response_model=S.ReorderRow)
def propose_recommendation(rec_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    row = conn.execute("SELECT * FROM recommendations WHERE id=?", (rec_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Recommendation not found")
    p = repo.get_product(conn, int(row["product_id"]))
    assert p
    oid = repo.create_reorder(
        conn,
        product_id=int(row["product_id"]),
        qty=int(row["suggested_qty"]),
        unit_cost_paise=int(p["unit_cost_paise"]),
        recommendation_id=rec_id,
        notes="Proposed from recommendation",
    )
    o = repo.get_reorder(conn, oid)
    assert o
    return _reorder_row(conn, o)


@router.post("/reorders", response_model=S.ReorderRow, status_code=201)
def create_reorder(body: S.ReorderCreateRequest, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    p = repo.get_product(conn, body.product_id)
    if not p or not int(p.get("is_active", 1)):
        raise HTTPException(404, "Product not found")
    qty = int(body.qty)
    if qty < 1:
        raise HTTPException(400, "Quantity must be at least 1")
    pack = max(1, int(p.get("pack_size") or 1))
    if qty % pack != 0:
        qty = max(pack, (qty // pack) * pack)
    oid = repo.create_reorder(
        conn,
        product_id=body.product_id,
        qty=qty,
        unit_cost_paise=int(p["unit_cost_paise"]),
        recommendation_id=body.recommendation_id,
        notes=body.notes or "Draft from What-If Simulator",
    )
    o = repo.get_reorder(conn, oid)
    assert o is not None
    return _reorder_row(conn, o)


@router.get("/reorders", response_model=list[S.ReorderRow])
def reorders(
    status: str | None = None, conn: sqlite3.Connection = Depends(get_db)
) -> Any:
    rows = repo.list_reorders(conn, status=status)
    return [
        {
            "id": r["id"],
            "product_id": r["product_id"],
            "sku": r.get("sku"),
            "product_name": r.get("product_name"),
            "qty": r["qty"],
            "status": r["status"],
            "created_at": r["created_at"],
            "unit_cost_paise": r["unit_cost_paise"],
            "total_paise": int(r["qty"]) * int(r["unit_cost_paise"]),
        }
        for r in rows
    ]


def _reorder_row(conn: sqlite3.Connection, o: dict) -> dict:
    p = repo.get_product(conn, int(o["product_id"]))
    return {
        "id": o["id"],
        "product_id": o["product_id"],
        "sku": p["sku"] if p else None,
        "product_name": p["name"] if p else None,
        "qty": o["qty"],
        "status": o["status"],
        "created_at": o["created_at"],
        "unit_cost_paise": o["unit_cost_paise"],
        "total_paise": int(o["qty"]) * int(o["unit_cost_paise"]),
    }


@router.post("/reorders/{reorder_id}/approve", response_model=S.ReorderRow)
def approve_reorder(reorder_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    try:
        o = repo.set_reorder_status(conn, reorder_id, "approved")
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return _reorder_row(conn, o)


@router.post("/reorders/{reorder_id}/reject", response_model=S.ReorderRow)
def reject_reorder(reorder_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    try:
        o = repo.set_reorder_status(conn, reorder_id, "rejected")
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return _reorder_row(conn, o)


@router.post("/reorders/{reorder_id}/receive", response_model=S.ReorderRow)
def receive_reorder(reorder_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    try:
        o = repo.set_reorder_status(conn, reorder_id, "received")
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return _reorder_row(conn, o)


@router.get("/agents", response_model=list[S.AgentCard])
def agents(conn: sqlite3.Connection = Depends(get_db)) -> Any:
    arts = {a["agent_name"]: a for a in artifacts.list_agent_artifacts()}
    versions = {v["agent_name"]: v for v in repo.list_model_versions(conn)}
    last_runs = conn.execute(
        """
        SELECT agent_name, MAX(started_at) AS last_run, AVG(duration_ms) AS avg_ms
        FROM agent_runs GROUP BY agent_name
        """
    ).fetchall()
    last_map = {r["agent_name"]: r for r in last_runs}
    cards = []
    for name in AGENT_ORDER:
        available = name in arts
        meta = {}
        if available:
            try:
                meta = artifacts.load_metadata(name, arts[name]["version"]) or {}
            except Exception:
                meta = {}
        lr = last_map.get(name)
        est = None
        if isinstance(meta, dict):
            est = meta.get("estimator") or meta.get("model")
        cards.append(
            {
                "id": name,
                "name": name.replace("_", " ").title(),
                "method": est if isinstance(est, str) else name,
                "data_source": getattr(get_agent(name), "provenance", "SYNTHETIC_DEMO"),
                "status": "active" if available else "unavailable",
                "artifact_available": available,
                "latency_median_ms": float(lr["avg_ms"]) if lr and lr["avg_ms"] is not None else None,
                "latency_p95_ms": None,  # Not measured at scale
                "last_run_at": lr["last_run"] if lr else None,
                "key_output": None,
                "confidence": None,  # Do not invent
            }
        )
    return cards


@router.get("/agent-runs")
def agent_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agent_name: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> Any:
    rows, _total = repo.list_agent_runs(
        conn, page=page, page_size=page_size, agent_name=agent_name
    )
    out = []
    for r in rows:
        agents = [a for a in (r.get("agents") or "").split(",") if a]
        out.append(
            {
                "trace_id": r["trace_id"],
                "scenario": "on_demand",
                "agents": agents,
                "status": r.get("status") or "ok",
                "started_at": r["started_at"],
                "duration_ms": r.get("total_duration_ms"),
                "recommendation": None,
            }
        )
    return out


@router.get("/agent-runs/{trace_id}", response_model=S.AgentRunTrace)
def agent_run_trace(trace_id: str, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    nodes_raw = repo.get_trace(conn, trace_id)
    if not nodes_raw:
        raise HTTPException(404, "Trace not found")
    nodes = []
    total = 0.0
    for n in nodes_raw:
        total += float(n.get("duration_ms") or 0)
        out_s = n.get("output_summary_json") or ""
        nodes.append(
            {
                "agent_id": n["agent_name"],
                "name": n["agent_name"].replace("_", " ").title(),
                "status": n["status"],
                "duration_ms": n.get("duration_ms"),
                "output_summary": out_s[:240] if isinstance(out_s, str) else str(out_s)[:240],
            }
        )
    return {
        "trace_id": trace_id,
        "nodes": nodes,
        "edges": DAG_EDGES,
        "status": "ok",
        "total_duration_ms": total,
    }


@router.post("/agent-runs/trigger", response_model=S.AgentRunTrace)
def trigger_run(body: S.TriggerRunRequest, conn: sqlite3.Connection = Depends(get_db)) -> Any:
    p = repo.get_product(conn, body.product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    try:
        result = run_decision(conn, body.product_id, persist_trace=True)
    except Exception as e:
        raise HTTPException(503, f"Decision run failed: {e}") from e
    tid = result.get("trace_id")
    if not tid:
        raise HTTPException(500, "No trace produced")
    return agent_run_trace(tid, conn)


def _read_json(path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


@router.get("/performance", response_model=S.PerformanceResponse)
def performance(conn: sqlite3.Connection = Depends(get_db)) -> Any:
    metrics = repo.list_metrics(conn)
    versions = repo.list_model_versions(conn)
    eval_path = settings.eval_dir / "latest_eval.json"
    eval_data: dict = {}
    if eval_path.exists():
        try:
            eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            eval_data = {}

    def metric_val(name: str, method: str = "demand_only"):
        for m in metrics:
            if m["metric_name"] == name and m["agent_name"] == method:
                return m.get("metric_value"), m.get("metric_display")
        return None, None

    wape, wape_d = metric_val("wape")
    mae, _ = metric_val("mae")
    biz = eval_data.get("business") or {}
    coverage = eval_data.get("coverage") or {}
    benchmark = _read_json(settings.eval_dir / "api_benchmark.json")
    expanded = _read_json(settings.eval_dir / "policy_replay_expanded.json")
    overview_p95 = None
    if benchmark:
        for endpoint in benchmark.get("endpoints") or []:
            if endpoint.get("name") == "analytics_overview":
                overview_p95 = endpoint.get("p95_ms")
                break

    # Prefer mean defined cost from policy replay when present
    multi_cost = None
    for row in biz.get("rows") or []:
        if row.get("strategy") == "multi_agent":
            multi_cost = row.get("cost_paise")
            break

    kpis = [
        {
            "id": "wape",
            "label": "Forecast WAPE (rolling 1-step holdout)",
            "value": wape if wape is not None else "N/A",
            "unit": None if wape is None else "ratio",
            "measured": wape is not None,
            "tooltip": eval_data.get("holdout_note")
            or "Chronological rolling one-step holdout on SYNTHETIC_DEMO",
            "source": "SYNTHETIC_DEMO",
        },
        {
            "id": "mae",
            "label": "Holdout MAE",
            "value": mae if mae is not None else "N/A",
            "measured": mae is not None,
            "source": "SYNTHETIC_DEMO",
        },
        {
            "id": "latency",
            "label": "Local analytics overview p95",
            "value": None if overview_p95 is None else round(float(overview_p95), 1),
            "unit": None if overview_p95 is None else "ms",
            "measured": overview_p95 is not None,
            "tooltip": (
                "Not measured. Run python scripts/benchmark_api.py to write a local TestClient sample."
                if overview_p95 is None
                else (
                    "In-process TestClient p95 for /api/analytics/overview. "
                    f"Measured at {benchmark.get('measured_at')}. Not a networked production SLO."
                )
            ),
            "source": "LOCAL_TESTCLIENT" if overview_p95 is not None else None,
        },
        {
            "id": "sim_policy_cost",
            "label": "Multi-agent mean defined cost",
            "value": multi_cost,
            "unit": "paise",
            "measured": multi_cost is not None,
            "source": "SIMULATED_POLICY_REPLAY",
            "tooltip": "Holding + shortage on identical SIMULATED paths — not retail savings",
        },
    ]

    baseline = []
    for row in eval_data.get("backtests") or []:
        baseline.append(
            {
                "name": row.get("method"),
                "wape": row.get("wape"),
                "mae": row.get("mae"),
            }
        )

    biz_rows = []
    for row in biz.get("rows") or []:
        biz_rows.append(
            {
                "strategy": row.get("strategy"),
                "savings_paise": None,  # never label cost as savings
                "cost_paise": row.get("cost_paise"),
                "mean_stockout_days": row.get("mean_stockout_days"),
                "mean_unmet_demand_units": row.get("mean_unmet_demand_units"),
                "note": row.get("note"),
            }
        )
    if not biz_rows and biz.get("total_suggested_cost_paise") is not None:
        biz_rows = [
            {
                "strategy": "legacy_suggested_spend",
                "savings_paise": None,
                "cost_paise": biz.get("total_suggested_cost_paise"),
                "note": "Suggested purchase cash — not savings",
            }
        ]

    business_simulation = {
        "label": biz.get("label", "SIMULATED_POLICY_REPLAY"),
        "sample_skus": biz.get("sample_skus"),
        "note": (
            "Policy comparison uses a small simulated sample. "
            "It does not establish that the multi-agent system is better in general."
        ),
        "rows": biz_rows,
    }
    agent_latency = [
        {
            "agent_name": row["agent_name"],
            "runs": int(row["n"]),
            "mean_duration_ms": float(row["avg_ms"]) if row["avg_ms"] is not None else None,
            "max_duration_ms": float(row["max_ms"]) if row["max_ms"] is not None else None,
        }
        for row in conn.execute(
            """
            SELECT agent_name, COUNT(*) AS n, AVG(duration_ms) AS avg_ms, MAX(duration_ms) AS max_ms
            FROM agent_runs
            GROUP BY agent_name
            ORDER BY agent_name
            """
        )
    ]

    model_versions = [
        {
            "name": v["agent_name"],
            "version": v["version"],
            "trained_at": v.get("trained_at"),
            "status": "deployed",
            "source": v.get("training_source"),
        }
        for v in versions
    ]

    series = eval_data.get("backtest_series") or []
    if not series:
        series_path = settings.eval_dir / "backtest_series.json"
        if series_path.exists():
            try:
                series = json.loads(series_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                series = []

    return {
        "kpis": kpis,
        "backtest_series": series,
        "baseline_comparison": baseline,
        "coverage": {
            "nominal": coverage.get("nominal", "p10–p90 ≈ 80%"),
            "empirical": coverage.get("empirical"),
            "pinball_loss": coverage.get("pinball_loss"),
        },
        "model_versions": model_versions,
        "business_simulation": business_simulation,
        "expanded_policy_replay": expanded,
        "api_benchmark": benchmark,
        "mlops": {
            "model_artifacts": artifacts.list_agent_artifacts(),
            "limitations": [
                "Category-level forecast accuracy is not stored as a separate metric.",
                "SKU-level forecast accuracy is not stored beyond the pooled holdout.",
                "Multi-horizon forecast scores are not stored; the backtest is rolling one-step.",
                "Policy replay is simulated and is not model accuracy.",
                "API latency is shown only after a local benchmark file is written.",
            ],
        },
        "agent_latency": agent_latency,
        "data_source": "SYNTHETIC_DEMO",
        "evaluation_mode": eval_data.get("evaluation_mode"),
    }
