# Agent dependency contract

Provenance: `SYNTHETIC_DEMO` sales unless noted `SIMULATED_SUPPLY`.

| Agent | Inputs | Outputs | Trained on | Consumer | Effect on decisions | Validation |
|---|---|---|---|---|---|---|
| calendar_effect | dow/dom/week/event | `calendar_uplift` (vs mid-week baseline) | train split sales | demand | adds bounded uplift to p50 | regression metrics on train |
| price_response | price, price_vs_median, promo | `expected_units_delta` vs shelf price | train split | demand, simulate | observational Δ units (not causal) | train regression; UI labeled |
| intermittence | recent zero-rate features | `p_zero_demand` | train | demand | shrinks p50 when p_zero≥0.35 | classifier metrics |
| sales_anomaly | demand feature row | `is_anomaly` | train IsolationForest | demand | blends p50 toward recent median | anomaly rate |
| product_similarity | 28d profile | `similarity_demand` | all SKU profiles | demand | sparse-data blend when p50 low | neighbor distances |
| demand | lag/roll/calendar/price feats + upstream kwargs | `p50_units`, `daily_p50` | train HGBR | interval, risk, optimizer, simulate | primary demand signal | holdout WAPE (rolling 1-step) |
| demand_interval | same feats + p50 | p10/p50/p90 series | quantile GBR train | risk (p90), forecasts table | uncertainty for risk features | holdout coverage when evaluated |
| supplier_eta | supplier history | `eta_days` / `lead_days` | synthetic lead labels | risk, optimizer | arrival timing | MAE on train |
| stockout_risk | **decision-time** stock, ROP, pack, demand, lead, qty, shelf, p90 | `stockout_risk` | `SIMULATED_SUPPLY` paths | optimizer `risk_fn(qty)` | candidate-specific shortage tilt | holdout Brier; leakage tests |
| excess_risk | same decision-time schema | `excess_risk` | `SIMULATED_SUPPLY` | optimizer `risk_fn(qty)` | candidate-specific excess tilt | holdout Brier; leakage tests |
| optimizer (deterministic) | demand, ETA, risks, pack, budget | `suggested_qty` | n/a | recommendations / UI | final order qty | constraint + oracle tests |

DAG order: calendar → price → intermittence → anomaly → similarity → **demand** → interval → ETA → risks → **optimizer**.

Failed/missing artifacts produce explicit `notices` and fallbacks; they are not silently counted as success.
