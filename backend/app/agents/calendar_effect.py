"""Calendar seasonality via Ridge on dow/dom/week."""

from __future__ import annotations

from sklearn.linear_model import Ridge

from app.agents.base import BaseAgent, TrainContext, eval_regression, panel_for_training

CAL_FEATS = ["dow", "dom", "week_of_year", "event_flag"]


class CalendarEffectAgent(BaseAgent):
    name = "calendar_effect"

    def fit(self, ctx: TrainContext) -> dict:
        split = panel_for_training(ctx.conn)
        tr = split.train
        cols = [c for c in CAL_FEATS if c in tr.columns]
        x = tr[cols].astype(float).fillna(0.0).values
        y = tr["target_units"].astype(float).values
        self.model = Ridge(alpha=1.0, random_state=42)
        self.model.fit(x, y)
        self.metadata = {"feature_columns": cols}
        return eval_regression(self.name, y, self.model.predict(x))

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        from datetime import datetime

        as_of = kwargs.get("as_of_date") or conn.execute(
            "SELECT MAX(sale_date) FROM sales WHERE product_id=?", (product_id,)
        ).fetchone()[0]
        if not as_of:
            return {"product_id": product_id, "calendar_lift": 0.0}
        dt = datetime.strptime(str(as_of)[:10], "%Y-%m-%d")
        import numpy as np

        x = np.array(
            [[dt.weekday(), dt.day, dt.isocalendar().week, float(kwargs.get("event_flag", 0))]],
            dtype=float,
        )
        lift = float(self.model.predict(x)[0])
        return {"product_id": product_id, "calendar_lift": lift, "as_of_date": str(as_of)[:10]}
