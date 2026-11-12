"""Demand point forecast agent."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from app.agents.base import (
    BaseAgent,
    TrainContext,
    eval_regression,
    n_jobs,
    panel_for_training,
)
from app.ml.features import FEATURE_COLUMNS, feature_matrix, load_sales_dataframe
from app.ml import features


class DemandAgent(BaseAgent):
    name = "demand"

    def fit(self, ctx: TrainContext) -> dict:
        split = panel_for_training(ctx.conn)
        tr = split.train
        if tr.empty:
            raise ValueError("No training rows for demand")
        x, y = feature_matrix(tr)
        params = dict(
            max_iter=80 if ctx.fast else 150,
            learning_rate=0.1,
            max_depth=4,
            random_state=42,
        )
        self.model = HistGradientBoostingRegressor(**params)
        self.model.fit(x, y)
        self.metadata = {"feature_columns": FEATURE_COLUMNS, **params}

        metrics = eval_regression(self.name, y, self.model.predict(x))
        if not split.holdout.empty:
            xh, yh = feature_matrix(split.holdout)
            metrics.update(
                {f"holdout_{k}": v for k, v in eval_regression(self.name, yh, self.model.predict(xh)).items()}
            )
        return metrics

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        sales = load_sales_dataframe(conn)
        sub = sales[sales["product_id"] == product_id]
        if sub.empty:
            return {"product_id": product_id, "p50_units": 0.0, "horizon_days": 28}
        feat = features.build_product_features(sub)
        if feat.empty:
            return {"product_id": product_id, "p50_units": 0.0, "horizon_days": 28}
        row = feat.iloc[-1:]
        cols = self.metadata.get("feature_columns", FEATURE_COLUMNS)
        x = row[[c for c in cols if c in row.columns]].astype(float).fillna(0.0).values
        p50 = float(max(0.0, self.model.predict(x)[0]))
        daily = []
        for i in range(28):
            daily.append({"day": i + 1, "p50_units": p50})
        return {"product_id": product_id, "p50_units": p50, "daily_p50": daily, "horizon_days": 28}
