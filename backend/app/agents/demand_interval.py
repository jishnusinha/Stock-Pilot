"""Demand interval forecast (p10/p90) with quantile GBRs."""

from __future__ import annotations

from sklearn.ensemble import GradientBoostingRegressor

from app.agents.base import BaseAgent, TrainContext, n_jobs, panel_for_training
from app.ml import features, metrics
from app.ml.features import FEATURE_COLUMNS, feature_matrix, load_sales_dataframe


class DemandIntervalAgent(BaseAgent):
    name = "demand_interval"

    def fit(self, ctx: TrainContext) -> dict:
        split = panel_for_training(ctx.conn)
        tr = split.train
        if tr.empty:
            raise ValueError("No training rows")
        x, y = feature_matrix(tr)
        n_est = 40 if ctx.fast else 80
        self.model = {
            "p10": GradientBoostingRegressor(
                loss="quantile",
                alpha=0.1,
                n_estimators=n_est,
                max_depth=3,
                random_state=42,
            ),
            "p90": GradientBoostingRegressor(
                loss="quantile",
                alpha=0.9,
                n_estimators=n_est,
                max_depth=3,
                random_state=43,
            ),
        }
        self.model["p10"].fit(x, y)
        self.model["p90"].fit(x, y)
        self.metadata = {"feature_columns": FEATURE_COLUMNS, "n_estimators": n_est}

        low = self.model["p10"].predict(x)
        high = self.model["p90"].predict(x)
        return {
            "pinball_p10": metrics.pinball_loss(y, low, 0.1),
            "pinball_p90": metrics.pinball_loss(y, high, 0.9),
            "coverage_train": metrics.interval_coverage(y, low, high),
        }

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        p50 = float(kwargs.get("p50_units", 0.0))
        sales = load_sales_dataframe(conn)
        sub = sales[sales["product_id"] == product_id]
        if sub.empty:
            p10, p90 = max(0.0, p50 * 0.6), p50 * 1.4
            p10, p50, p90 = metrics.reconcile_quantiles(p10, p50, p90)
            return {"product_id": product_id, "p10_units": p10, "p50_units": p50, "p90_units": p90}

        feat = features.build_product_features(sub)
        row = feat.iloc[-1:]
        cols = self.metadata.get("feature_columns", FEATURE_COLUMNS)
        x = row[[c for c in cols if c in row.columns]].astype(float).fillna(0.0).values
        p10 = float(max(0.0, self.model["p10"].predict(x)[0]))
        p90 = float(max(0.0, self.model["p90"].predict(x)[0]))
        if p50 <= 0:
            p50 = float((p10 + p90) / 2)
        p10, p50, p90 = metrics.reconcile_quantiles(p10, p50, p90)
        series = []
        for i in range(28):
            series.append(
                {
                    "target_date_offset": i + 1,
                    "p10_units": p10,
                    "p50_units": p50,
                    "p90_units": p90,
                }
            )
        return {
            "product_id": product_id,
            "p10_units": p10,
            "p50_units": p50,
            "p90_units": p90,
            "forecast_series": series,
        }
