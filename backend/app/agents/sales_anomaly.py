"""Sales anomaly detection via IsolationForest."""

from __future__ import annotations

from sklearn.ensemble import IsolationForest

from app.agents.base import BaseAgent, TrainContext, panel_for_training
from app.ml import features
from app.ml.features import FEATURE_COLUMNS, feature_matrix, load_sales_dataframe


class SalesAnomalyAgent(BaseAgent):
    name = "sales_anomaly"

    def fit(self, ctx: TrainContext) -> dict:
        split = panel_for_training(ctx.conn)
        tr = split.train
        x, _ = feature_matrix(tr)
        self.model = IsolationForest(
            n_estimators=60 if ctx.fast else 100,
            contamination=0.05,
            random_state=42,
            n_jobs=1,
        )
        self.model.fit(x)
        self.metadata = {"feature_columns": FEATURE_COLUMNS}
        scores = self.model.decision_function(x)
        flagged = int((self.model.predict(x) == -1).sum())
        return {"anomaly_rate_train": flagged / max(1, len(x)), "mean_score": float(scores.mean())}

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        sales = load_sales_dataframe(conn)
        sub = sales[sales["product_id"] == product_id]
        if sub.empty:
            return {"product_id": product_id, "is_anomaly": False, "anomaly_score": 0.0}
        feat = features.build_product_features(sub)
        row = feat.iloc[-1:]
        cols = self.metadata.get("feature_columns", FEATURE_COLUMNS)
        x = row[[c for c in cols if c in row.columns]].astype(float).fillna(0.0).values
        pred = int(self.model.predict(x)[0])
        score = float(self.model.decision_function(x)[0])
        return {
            "product_id": product_id,
            "is_anomaly": pred == -1,
            "anomaly_score": score,
        }
