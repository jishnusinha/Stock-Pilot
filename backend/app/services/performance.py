"""Persist evaluation metrics and simulated business outcomes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.core.config import settings
from app.db import repositories as repo
from app.ml.backtest import run_backtests


SIMULATED = "SIMULATED"


def evaluate_all(conn: sqlite3.Connection, *, agents_version: str = "ensemble") -> dict:
    settings.ensure_dirs()
    split = "holdout"
    repo.clear_metrics_for_eval(conn, split)
    results = run_backtests(conn)
    for row in results:
        for metric in ("wape", "mae", "rmse"):
            repo.insert_metric(
                conn,
                {
                    "agent_name": row["method"],
                    "version": agents_version,
                    "metric_name": metric,
                    "metric_value": row.get(metric),
                    "evaluation_split": split,
                    "dataset_source": "SYNTHETIC_DEMO",
                    "metric_display": _disp(metric, row.get(metric)),
                },
            )

    biz = _simulated_business_outcomes(conn)
    out_path = settings.eval_dir / "latest_eval.json"
    payload = {"backtests": results, "business": biz, "split": split}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    conn.commit()
    return payload


def _disp(name: str, val) -> str:
    from app.ml.metrics import metric_display

    return metric_display(name, val)


def _simulated_business_outcomes(conn: sqlite3.Connection) -> dict:
    """Label SIMULATED — aggregate reorder suggestions on sample SKUs."""
    from app.services.orchestrator import run_decision

    ids = conn.execute("SELECT id FROM products ORDER BY id LIMIT 5").fetchall()
    total_cost = 0
    stockout = 0.0
    for r in ids:
        try:
            dec = run_decision(conn, int(r["id"]), persist_trace=False)
            total_cost += int(dec.get("estimated_cost_paise") or 0)
            stockout += float(dec.get("expected_stockout_risk") or 0)
        except Exception:
            continue
    return {
        "label": SIMULATED,
        "sample_skus": len(ids),
        "total_suggested_cost_paise": total_cost,
        "mean_stockout_risk": stockout / max(1, len(ids)),
    }
