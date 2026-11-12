"""Persist evaluation metrics and simulated business outcomes."""

from __future__ import annotations

import json
import sqlite3

from app.core.config import settings
from app.db import repositories as repo
from app.ml.backtest import run_backtests
from app.services.policy_replay import evaluate_policy_replay


SIMULATED = "SIMULATED"


def evaluate_all(conn: sqlite3.Connection, *, agents_version: str = "ensemble") -> dict:
    settings.ensure_dirs()
    split = "holdout"
    repo.clear_metrics_for_eval(conn, split)
    results = run_backtests(conn, include_series=True)
    for row in results:
        for metric in ("wape", "mae", "rmse"):
            if row.get(metric) is None and row.get("method") == "full_decision_system":
                continue
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

    # Aggregate chart series from demand_only (daily actual vs predicted)
    series_chart = _series_for_chart(results)
    coverage = _interval_coverage_if_available(conn)

    biz = evaluate_policy_replay(conn, sample=5)
    # Also keep legacy suggested-spend sample for transparency
    legacy = _suggested_spend_sample(conn)
    biz["legacy_suggested_spend"] = legacy

    out_path = settings.eval_dir / "latest_eval.json"
    payload = {
        "backtests": [
            {k: v for k, v in r.items() if k != "series"} for r in results
        ],
        "backtest_series": series_chart,
        "coverage": coverage,
        "business": biz,
        "split": split,
        "evaluation_mode": "rolling_one_step_holdout",
        "holdout_note": "Demand model scored on chronological holdout rows; not mean-holdout.",
    }
    # Persist full series separately (can be large)
    series_path = settings.eval_dir / "backtest_series.json"
    series_path.write_text(json.dumps(series_chart, indent=2), encoding="utf-8")
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    conn.commit()
    return payload


def _series_for_chart(results: list[dict], max_points: int = 120) -> list[dict]:
    demand = next((r for r in results if r.get("method") == "demand_only"), None)
    if not demand or not demand.get("series"):
        return []
    # Aggregate by target_date across products (mean actual/pred) for readable chart
    by_date: dict[str, list[tuple[float, float]]] = {}
    for rec in demand["series"]:
        by_date.setdefault(rec["target_date"], []).append(
            (float(rec["actual"]), float(rec["prediction"]))
        )
    out = []
    for date in sorted(by_date.keys()):
        pairs = by_date[date]
        out.append(
            {
                "date": date,
                "actual": float(sum(a for a, _ in pairs) / len(pairs)),
                "predicted": float(sum(p for _, p in pairs) / len(pairs)),
                "n_skus": len(pairs),
            }
        )
        if len(out) >= max_points:
            break
    return out


def _interval_coverage_if_available(conn: sqlite3.Connection) -> dict:
    """Compute empirical p10–p90 coverage on holdout when interval model is loadable."""
    try:
        from app.agents.demand_interval import DemandIntervalAgent
        from app.ml import features, metrics, splits
        from app.ml.features import FEATURE_COLUMNS, load_sales_dataframe

        agent = DemandIntervalAgent()
        agent.load()
        sales = load_sales_dataframe(conn)
        if sales.empty:
            return {"nominal": "p10–p90 ≈ 80%", "empirical": None, "pinball_loss": None}
        feat = features.build_panel_features(sales)
        ho = splits.split_panel(feat).holdout
        if ho.empty:
            return {"nominal": "p10–p90 ≈ 80%", "empirical": None, "pinball_loss": None}
        cols = agent.metadata.get("feature_columns", FEATURE_COLUMNS)
        present = [c for c in cols if c in ho.columns]
        x = ho[present].astype(float).fillna(0.0).values
        y = ho["target_units"].astype(float).values
        low = agent.model["p10"].predict(x)
        high = agent.model["p90"].predict(x)
        return {
            "nominal": "p10–p90 ≈ 80%",
            "empirical": metrics.interval_coverage(y, low, high),
            "pinball_loss": metrics.pinball_loss(y, low, 0.1),
            "n": int(len(y)),
            "split": "holdout",
        }
    except Exception:
        return {"nominal": "p10–p90 ≈ 80%", "empirical": None, "pinball_loss": None}


def _disp(name: str, val) -> str:
    from app.ml.metrics import metric_display

    return metric_display(name, val)


def _suggested_spend_sample(conn: sqlite3.Connection) -> dict:
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
        "note": "Suggested purchase cash — not realized savings",
    }
