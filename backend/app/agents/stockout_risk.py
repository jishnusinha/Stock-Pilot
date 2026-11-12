"""Stockout risk classifier on simulated supply scenarios."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from app.agents.base import PROVENANCE_SIMULATED, BaseAgent, TrainContext, n_jobs
from app.agents.sim_supply import simulate_scenarios


class StockoutRiskAgent(BaseAgent):
    name = "stockout_risk"
    provenance = PROVENANCE_SIMULATED

    def fit(self, ctx: TrainContext) -> dict:
        rng = np.random.default_rng(42)
        products = ctx.conn.execute(
            "SELECT id, stock_on_hand, reorder_point, pack_size, shelf_life_days FROM products LIMIT ?",
            (80 if ctx.fast else 500,),
        ).fetchall()
        xs, ys = [], []
        for p in products:
            avg = ctx.conn.execute(
                "SELECT AVG(units) FROM sales WHERE product_id=?", (p["id"],)
            ).fetchone()[0]
            lead = ctx.conn.execute(
                "SELECT base_lead_days FROM suppliers s JOIN products pr ON pr.supplier_id=s.id WHERE pr.id=?",
                (p["id"],),
            ).fetchone()
            ld = int(lead["base_lead_days"]) if lead else 7
            x, y, _ = simulate_scenarios(
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
            ys.append(y)
        x_all = np.vstack(xs)
        y_all = np.concatenate(ys)
        self.model = HistGradientBoostingClassifier(
            max_iter=60 if ctx.fast else 100,
            random_state=42,
        )
        self.model.fit(x_all, y_all)
        self.metadata = {"feature_dim": x_all.shape[1], "source": PROVENANCE_SIMULATED}
        prob = self.model.predict_proba(x_all)[:, 1]
        from app.ml import metrics

        return {"brier_train": metrics.brier_score(y_all, prob)}

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        prod = conn.execute(
            "SELECT stock_on_hand, reorder_point, pack_size, shelf_life_days FROM products WHERE id=?",
            (product_id,),
        ).fetchone()
        if not prod:
            return {"product_id": product_id, "stockout_risk": 0.0}
        avg = conn.execute("SELECT AVG(units) FROM sales WHERE product_id=?", (product_id,)).fetchone()[0]
        eta = float(kwargs.get("eta_days", kwargs.get("lead_days", 7)))
        order_qty = int(kwargs.get("order_qty", prod["pack_size"]))
        feat = np.array(
            [
                [
                    prod["stock_on_hand"],
                    prod["reorder_point"],
                    prod["pack_size"],
                    float(avg or 1.0),
                    eta,
                    order_qty,
                    0,
                    prod["stock_on_hand"],
                    0.0,
                ]
            ],
            dtype=float,
        )
        p = float(self.model.predict_proba(feat)[0, 1])
        return {"product_id": product_id, "stockout_risk": p, "provenance": PROVENANCE_SIMULATED}
