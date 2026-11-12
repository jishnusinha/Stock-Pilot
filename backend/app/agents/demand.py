"""Demand point forecast agent."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from app.agents.base import (
    BaseAgent,
    TrainContext,
    eval_regression,
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
                {
                    f"holdout_{k}": v
                    for k, v in eval_regression(self.name, yh, self.model.predict(xh)).items()
                }
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

        row = feat.iloc[-1:].copy()
        cols = self.metadata.get("feature_columns", FEATURE_COLUMNS)

        # Optional what-if / upstream conditioning on the inference feature row
        proposed_price = kwargs.get("proposed_price_paise")
        if proposed_price is not None and "price_paise" in row.columns:
            price = float(proposed_price)
            med = float(sub["selling_price_paise"].median() or price or 1.0)
            row["price_paise"] = price
            row["price_vs_median"] = price / (med or 1.0)

        cal_uplift = float(kwargs.get("calendar_uplift", 0.0) or 0.0)
        price_delta = float(kwargs.get("price_units_delta", 0.0) or 0.0)
        p_zero = float(kwargs.get("p_zero_demand", 0.0) or 0.0)
        is_anomaly = bool(kwargs.get("is_anomaly", False))
        similarity_blend = kwargs.get("similarity_demand")

        x = row[[c for c in cols if c in row.columns]].astype(float).fillna(0.0).values
        p50 = float(max(0.0, self.model.predict(x)[0]))

        # Apply validated upstream adjustments (bounded)
        p50 = max(0.0, p50 + cal_uplift + price_delta)
        if p_zero >= 0.35:
            # Intermittence: shrink toward zero-demand likelihood
            p50 = p50 * (1.0 - 0.5 * min(1.0, p_zero))
        if is_anomaly:
            # Conservative: blend toward recent median
            recent = float(sub["units"].tail(28).median()) if len(sub) else p50
            p50 = 0.5 * p50 + 0.5 * recent
        if similarity_blend is not None and p50 < 0.5:
            p50 = 0.7 * p50 + 0.3 * float(similarity_blend)

        # Mild horizon shape from day-of-week of successive future days (not flat clone)
        import pandas as pd

        last_date = pd.Timestamp(feat["sale_date"].iloc[-1])
        daily = []
        for i in range(28):
            # Use dow cyclical mild modulation around p50 (±8%) without claiming causal calendar
            dow = int((last_date + pd.Timedelta(days=i + 1)).dayofweek)
            factor = 1.0 + 0.08 * np.sin(2 * np.pi * dow / 7.0)
            daily.append({"day": i + 1, "p50_units": float(max(0.0, p50 * factor))})

        return {
            "product_id": product_id,
            "p50_units": p50,
            "daily_p50": daily,
            "horizon_days": 28,
            "adjustments": {
                "calendar_uplift": cal_uplift,
                "price_units_delta": price_delta,
                "p_zero_demand": p_zero,
                "is_anomaly": is_anomaly,
                "proposed_price_paise": proposed_price,
            },
        }
