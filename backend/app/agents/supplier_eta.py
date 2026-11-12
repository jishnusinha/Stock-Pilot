"""Supplier lead-time ETA regressor."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from app.agents.base import BaseAgent, TrainContext, eval_regression, n_jobs


class SupplierEtaAgent(BaseAgent):
    name = "supplier_eta"

    def fit(self, ctx: TrainContext) -> dict:
        rows = ctx.conn.execute(
            """
            SELECT s.base_lead_days, s.delivery_reliability, p.category,
                   AVG(sl.units) AS avg_units
            FROM products p
            JOIN suppliers s ON s.id = p.supplier_id
            JOIN sales sl ON sl.product_id = p.id
            GROUP BY p.supplier_id, p.category, s.base_lead_days, s.delivery_reliability
            """
        ).fetchall()
        if not rows:
            raise ValueError("No supplier stats")
        cats = sorted({r["category"] for r in rows})
        cat_idx = {c: i for i, c in enumerate(cats)}
        x, y = [], []
        for r in rows:
            vec = [
                float(r["base_lead_days"]),
                float(r["delivery_reliability"]),
                float(r["avg_units"] or 0),
            ] + [1.0 if cat_idx[r["category"]] == i else 0.0 for i in range(len(cats))]
            # synthetic realized lead time around base with noise
            eta = float(r["base_lead_days"]) * (1.1 - 0.2 * float(r["delivery_reliability"]))
            x.append(vec)
            y.append(eta)
        x_arr, y_arr = np.array(x), np.array(y)
        n_est = 30 if ctx.fast else 60
        self.model = RandomForestRegressor(
            n_estimators=n_est,
            max_depth=6,
            random_state=42,
            n_jobs=n_jobs(ctx.threads),
        )
        self.model.fit(x_arr, y_arr)
        self.metadata = {"categories": cats, "n_estimators": n_est}
        return eval_regression(self.name, y_arr, self.model.predict(x_arr))

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        row = conn.execute(
            """
            SELECT p.category, s.base_lead_days, s.delivery_reliability,
                   (SELECT AVG(units) FROM sales WHERE product_id=p.id) AS avg_units
            FROM products p JOIN suppliers s ON s.id=p.supplier_id WHERE p.id=?
            """,
            (product_id,),
        ).fetchone()
        if not row:
            return {"product_id": product_id, "eta_days": 7.0}
        cats = self.metadata.get("categories", [])
        vec = [
            float(row["base_lead_days"]),
            float(row["delivery_reliability"]),
            float(row["avg_units"] or 0),
        ]
        cat_idx = {c: i for i, c in enumerate(cats)}
        for c in cats:
            vec.append(1.0 if cat_idx.get(row["category"]) == cat_idx.get(c) else 0.0)
        eta = float(max(1.0, self.model.predict([vec])[0]))
        return {"product_id": product_id, "eta_days": eta, "lead_days": int(round(eta))}
