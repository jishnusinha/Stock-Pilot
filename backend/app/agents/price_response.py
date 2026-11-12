"""Observational price-response proxy via Ridge / ElasticNet.

IMPORTANT: Estimates are observational associations on SYNTHETIC_DEMO data,
not identified causal price elasticities. Outputs are labeled accordingly.
"""

from __future__ import annotations

from sklearn.linear_model import ElasticNet, Ridge

from app.agents.base import BaseAgent, TrainContext, eval_regression, panel_for_training
from app.ml.features import load_sales_dataframe

PRICE_FEATS = ["price_paise", "price_vs_median", "promo_flag"]


class PriceResponseAgent(BaseAgent):
    name = "price_response"

    def fit(self, ctx: TrainContext) -> dict:
        split = panel_for_training(ctx.conn)
        tr = split.train
        cols = [c for c in PRICE_FEATS if c in tr.columns]
        x = tr[cols].astype(float).fillna(0.0).values
        y = tr["target_units"].astype(float).values
        if ctx.fast:
            self.model = Ridge(alpha=1.0, random_state=42)
        else:
            self.model = ElasticNet(alpha=0.05, l1_ratio=0.3, max_iter=500, random_state=42)
        self.model.fit(x, y)
        self.metadata = {
            "feature_columns": cols,
            "effect_type": "observational_association",
            "not_causal_elasticity": True,
        }
        return eval_regression(self.name, y, self.model.predict(x))

    def predict_one(self, conn, product_id: int, **kwargs) -> dict:
        prod = conn.execute(
            "SELECT selling_price_paise FROM products WHERE id=?", (product_id,)
        ).fetchone()
        baseline_price = float(prod["selling_price_paise"]) if prod else 0.0
        proposed = kwargs.get("proposed_price_paise")
        price = float(proposed) if proposed is not None else baseline_price

        sales = load_sales_dataframe(conn)
        sub = sales[sales["product_id"] == product_id]
        med = float(sub["selling_price_paise"].median()) if not sub.empty else price or 1.0
        promo = float(kwargs.get("promo_flag", 0))

        level_proposed = float(self.model.predict(np_row(price, med, promo))[0])
        level_baseline = float(self.model.predict(np_row(baseline_price, med, promo))[0])
        delta = level_proposed - level_baseline

        # Bound implausible observational responses
        delta = float(max(-level_baseline * 0.5, min(level_baseline * 0.5, delta)))

        return {
            "product_id": product_id,
            "expected_units_level": level_proposed,
            "baseline_units_level": level_baseline,
            "expected_units_delta": delta,
            "price_paise": int(price),
            "baseline_price_paise": int(baseline_price),
            "effect_type": "observational_association",
            "not_causal_elasticity": True,
        }


def np_row(price: float, med: float, promo: float):
    import numpy as np

    return np.array([[price, price / (med or 1.0), promo]], dtype=float)
