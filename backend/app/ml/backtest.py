"""Holdout backtests for baselines and agents."""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from app.ml import baselines, features, metrics, splits
from app.ml.features import load_sales_dataframe


def _holdout_eval(conn: sqlite3.Connection, method: str) -> dict:
    sales = load_sales_dataframe(conn)
    if sales.empty:
        return {"method": method, "wape": None, "mae": None, "n": 0}
    feat = features.build_panel_features(sales)
    sp = splits.split_panel(feat)
    ho = sp.holdout
    if ho.empty:
        return {"method": method, "wape": None, "mae": None, "n": 0}

    preds, actuals = [], []
    for pid, grp in sales.groupby("product_id"):
        grp = grp.sort_values("sale_date")
        if method == "demand_only":
            from app.agents.demand import DemandAgent

            agent = DemandAgent()
            try:
                agent.load()
                p50 = agent.predict(conn, int(pid)).output.get("p50_units", 0.0)
            except FileNotFoundError:
                p50 = baselines.moving_average_28(grp["units"])
            ho_pid = ho[ho["product_id"] == pid]
            for _ in range(len(ho_pid)):
                preds.append(p50)
                actuals.append(ho_pid["target_units"].mean())
            continue

        ho_dates = set(pd.to_datetime(ho[ho["product_id"] == pid]["sale_date"]))
        for _, row in grp.iterrows():
            if pd.to_datetime(row["sale_date"]) not in ho_dates:
                continue
            hist = grp[grp["sale_date"] < row["sale_date"]]["units"]
            if method == "seasonal_naive_7":
                preds.append(baselines.seasonal_naive_7(hist))
            elif method == "moving_average_28":
                preds.append(baselines.moving_average_28(hist))
            else:
                preds.append(baselines.moving_average_28(hist))
            actuals.append(float(row["units"]))

    y_true = np.array(actuals, dtype=float)
    y_pred = np.array(preds, dtype=float)
    return {
        "method": method,
        "wape": metrics.wape(y_true, y_pred),
        "mae": metrics.mae(y_true, y_pred),
        "rmse": metrics.rmse(y_true, y_pred),
        "n": int(len(y_true)),
    }


def run_backtests(conn: sqlite3.Connection) -> list[dict]:
    methods = ["seasonal_naive_7", "moving_average_28", "demand_only", "full_decision_system"]
    out = []
    for m in methods:
        if m == "full_decision_system":
            out.append(
                {
                    "method": m,
                    "wape": None,
                    "mae": None,
                    "n": 0,
                    "note": "business metrics in performance.evaluate SIMULATED",
                }
            )
        else:
            out.append(_holdout_eval(conn, m))
    return out
