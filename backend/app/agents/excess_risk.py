"""Excess inventory risk on simulated trajectories (no outcome leakage)."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split

from app.agents.base import PROVENANCE_SIMULATED, BaseAgent, TrainContext
from app.agents.sim_supply import (
    DECISION_TIME_FEATURES,
    FEATURE_SCHEMA_VERSION,
    decision_time_feature_vector,
    simulate_scenarios,
)


class ExcessRiskAgent(BaseAgent):
    name = "excess_risk"
    provenance = PROVENANCE_SIMULATED

    def fit(self, ctx: TrainContext) -> dict:
        rng = np.random.default_rng(43)
        products = ctx.conn.execute(
            "SELECT id, stock_on_hand, reorder_point, pack_size, shelf_life_days FROM products LIMIT ?",
            (80 if ctx.fast else 500,),
        ).fetchall()
        xs, ye = [], []
        for p in products:
            avg = ctx.conn.execute(
                "SELECT AVG(units) FROM sales WHERE product_id=?", (p["id"],)
            ).fetchone()[0]
            lead = ctx.conn.execute(
                "SELECT base_lead_days FROM suppliers s JOIN products pr ON pr.supplier_id=s.id WHERE pr.id=?",
                (p["id"],),
            ).fetchone()
            ld = int(lead["base_lead_days"]) if lead else 7
            x, _, y, _ = simulate_scenarios(
                rng,
                8 if ctx.fast else 15,
                stock=int(p["stock_on_hand"]),
                reorder_point=int(p["reorder_point"]),
                pack_size=int(p["pack_size"]),
                daily_demand=float(avg or 1.0),
                lead_days=ld,
                shelf_life=p["shelf_life_days"],
            )
            xs.append(x)
            ye.append(y)
        x_all = np.vstack(xs)
        y_all = np.concatenate(ye)
        if len(y_all) >= 20 and len(np.unique(y_all)) > 1:
            x_tr, x_te, y_tr, y_te = train_test_split(
                x_all, y_all, test_size=0.25, random_state=44, stratify=y_all
            )
        else:
            x_tr, y_tr, x_te, y_te = x_all, y_all, x_all, y_all

        self.model = HistGradientBoostingClassifier(
            max_iter=60 if ctx.fast else 100, random_state=44
        )
        self.model.fit(x_tr, y_tr)
        self.metadata = {
            "feature_dim": int(x_all.shape[1]),
            "feature_columns": list(DECISION_TIME_FEATURES),
            "schema_version": FEATURE_SCHEMA_VERSION,
            "source": PROVENANCE_SIMULATED,
        }
        from app.ml import metrics

        prob = self.model.predict_proba(x_te)[:, 1]
        return {
            "brier_holdout": metrics.brier_score(y_te, prob),
            "n_train": int(len(y_tr)),
            "n_eval": int(len(y_te)),
        }

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        prod = conn.execute(
            "SELECT stock_on_hand, reorder_point, pack_size, shelf_life_days FROM products WHERE id=?",
            (product_id,),
        ).fetchone()
        if not prod:
            return {"product_id": product_id, "excess_risk": 0.0}
        avg = conn.execute(
            "SELECT AVG(units) FROM sales WHERE product_id=?", (product_id,)
        ).fetchone()[0]
        eta = float(kwargs.get("eta_days", kwargs.get("lead_days", 7)))
        order_qty = int(kwargs.get("order_qty", prod["pack_size"]))
        daily = float(kwargs.get("daily_demand", avg or 1.0))
        demand_p90 = float(kwargs.get("demand_p90", daily * 1.25))
        feat = decision_time_feature_vector(
            stock=prod["stock_on_hand"],
            reorder_point=prod["reorder_point"],
            pack_size=prod["pack_size"],
            daily_demand=daily,
            lead_days=eta,
            order_qty=order_qty,
            shelf_life_days=prod["shelf_life_days"],
            demand_p90=demand_p90,
        ).reshape(1, -1)
        expected = self.metadata.get("feature_columns", list(DECISION_TIME_FEATURES))
        if feat.shape[1] != len(expected):
            raise ValueError(
                f"excess_risk feature dim {feat.shape[1]} != schema {len(expected)}"
            )
        p = float(self.model.predict_proba(feat)[0, 1])
        return {
            "product_id": product_id,
            "excess_risk": p,
            "provenance": PROVENANCE_SIMULATED,
            "schema_version": FEATURE_SCHEMA_VERSION,
        }
