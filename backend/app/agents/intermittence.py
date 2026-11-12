"""Zero-demand (intermittence) classifier."""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

from app.agents.base import BaseAgent, TrainContext, panel_for_training
from app.ml import features, metrics
from app.ml.features import FEATURE_COLUMNS, feature_matrix, load_sales_dataframe


class IntermittenceAgent(BaseAgent):
    name = "intermittence"

    def fit(self, ctx: TrainContext) -> dict:
        split = panel_for_training(ctx.conn)
        tr = split.train
        x, y_units = feature_matrix(tr)
        y = (y_units == 0).astype(int)
        self.model = LogisticRegression(max_iter=800, class_weight="balanced", random_state=42)
        self.model.fit(x, y)
        self.metadata = {"feature_columns": FEATURE_COLUMNS}
        prob = self.model.predict_proba(x)[:, 1]
        return {"brier_train": metrics.brier_score(y, prob)}

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        sales = load_sales_dataframe(conn)
        sub = sales[sales["product_id"] == product_id]
        if sub.empty:
            return {"product_id": product_id, "p_zero_demand": 0.5}
        feat = features.build_product_features(sub)
        row = feat.iloc[-1:]
        cols = self.metadata.get("feature_columns", FEATURE_COLUMNS)
        x = row[[c for c in cols if c in row.columns]].astype(float).fillna(0.0).values
        p = float(self.model.predict_proba(x)[0, 1])
        return {"product_id": product_id, "p_zero_demand": p, "is_intermittent": p >= 0.35}
