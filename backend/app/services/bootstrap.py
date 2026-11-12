"""One-shot environment bootstrap."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app.agents.base import TrainContext
from app.agents.registry import train_all
from app.core.config import settings
from app.db.connection import connect
from app.db.migrations import migrate
from app.db import repositories as repo
from app.ml import artifacts
from app.services.performance import evaluate_all
from app.services.seed import seed_demo
from app.services.orchestrator import run_decision


def bootstrap(
    *,
    products: int = 200,
    days: int = 365,
    seed: int | None = None,
    threads: int = 2,
    fast: bool = False,
    force: bool = False,
) -> dict:
    seed = seed if seed is not None else settings.seed
    settings.ensure_dirs()
    conn = connect()
    try:
        migrate(conn)
        n = repo.count_products(conn)
        if n == 0 or force:
            if force and settings.db_path.exists():
                conn.close()
                settings.db_path.unlink(missing_ok=True)
                conn = connect()
                migrate(conn)
            seed_info = seed_demo(conn, products=products, days=days, seed=seed)
        else:
            seed_info = {"skipped": True, "products_in_db": n}

        have_models = bool(artifacts.list_agent_artifacts())
        if not have_models or force:
            train_results = train_all(
                TrainContext(conn=conn, fast=fast, threads=threads)
            )
        else:
            train_results = [{"skipped": True}]

        # Precompute forecasts/risk for all products (persist traces for a sample)
        ids = conn.execute("SELECT id FROM products WHERE is_active=1 ORDER BY id").fetchall()
        traces = []
        n_ok = 0
        for i, r in enumerate(ids):
            persist = i < 12  # keep DB traces bounded
            try:
                dec = run_decision(conn, int(r["id"]), persist_trace=persist)
                repo.insert_recommendation(
                    conn,
                    {
                        "product_id": int(r["id"]),
                        "suggested_qty": dec["suggested_qty"],
                        "expected_stockout_risk": dec["expected_stockout_risk"],
                        "expected_excess_risk": dec["expected_excess_risk"],
                        "estimated_cost_paise": dec["estimated_cost_paise"],
                        "expected_arrival_date": dec["expected_arrival_date"],
                        "explanation_json": dec["explanation"],
                        "trace_id": dec["trace_id"],
                    },
                )
                n_ok += 1
                if persist:
                    traces.append(dec["trace_id"])
            except Exception:
                continue
            if (i + 1) % 25 == 0:
                conn.commit()

        eval_payload = evaluate_all(conn)
        conn.commit()
        return {
            "seed": seed_info,
            "training": [
                (
                    {"agent": r.agent_name, "status": r.status, "version": r.model_version}
                    if hasattr(r, "agent_name")
                    else r
                )
                for r in train_results
            ],
            "decisions_ok": n_ok,
            "sample_traces": traces[:5],
            "evaluation": {
                "backtests": (eval_payload.get("backtests") or [])[:4],
                "business": eval_payload.get("business"),
            },
        }
    finally:
        conn.close()


def reset_demo(*, confirm: bool = False) -> None:
    if not confirm:
        raise SystemExit("Pass --confirm to reset demo data")
    for p in [settings.db_path, settings.db_path.with_suffix(".db-wal"), settings.db_path.with_suffix(".db-shm")]:
        p.unlink(missing_ok=True)
    if settings.model_dir.exists():
        shutil.rmtree(settings.model_dir, ignore_errors=True)
    settings.ensure_dirs()
