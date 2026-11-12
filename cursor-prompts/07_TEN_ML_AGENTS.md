# Phase 07 — Train and save the 10 real non-LLM ML agents

## Definition of an agent
An agent is a small **fitted model** plus a typed inference interface and metadata. Agents can share raw/features/other agents' outputs. A plain Python if-statement is not itself one of the ten ML models. Train one at a time on local synthetic data and persist fitted artifacts; no pretrained model downloads. `app/agents/base.py` exports a common `AgentResult` with fields `{name, version, source, input_summary, output, warnings, elapsed_ms}` and a `predict(...)` method.

## Ten actual agents (required; methods may be replaced with equal-resource documented alternatives)
| ID | Agent key | Model / fit data | Output and dependency |
|---|---|---|---|
| 01 | `demand` | `HistGradientBoostingRegressor` on historical daily SKU sales + lagged/calendar features | Nonnegative expected next-day units; used in 7/28-day demand projection. Fit on `SYNTHETIC_DEMO` sales. |
| 02 | `demand_interval` | 2 `GradientBoostingRegressor(loss='quantile', alpha=.10/.90)` small trees or supported HistGB quantile equivalent | p10/p90 uncertainty for daily unit demand; depends on same lag feature contract; evaluate pinball and coverage. |
| 03 | `intermittence` | `LogisticRegression` or compact `HistGradientBoostingClassifier` predicting `units==0` | P(zero sale) and demand sparsity adjustment, used by demand scenario; no fake confidence. |
| 04 | `price_response` | Small `Ridge`/`ElasticNet` fitted on synthetic price-varied demand and relevant controls | Direction/magnitude of **simulated association** between price and demand; avoid claiming causal elasticity on real shoppers. |
| 05 | `calendar_effect` | Ridge with encoded day-of-week/month/event/promo and lag baseline | Seasonal/calendar adjustment to demand; explicit trained regression. |
| 06 | `sales_anomaly` | `IsolationForest` on normalized sales residuals, rolling volatility and promo flags | Anomaly score + flag, not an invented probability; show observed unusual SKUs. |
| 07 | `product_similarity` | `NearestNeighbors` trained on compact, normalized product behavior embeddings (aggregate demand, CV, intermittent ratio, category indicators) | Similar products and distances. Unsupervised fitted model counts as ML. |
| 08 | `supplier_eta` | Small `RandomForestRegressor(n_estimators<=60, n_jobs<=2)` on generated delivery samples | Expected delivery days, simulator provenance. |
| 09 | `stockout_risk` | `HistGradientBoostingClassifier` on **simulated** inventory scenarios (stock, demand forecast, uncertainty, order qty, lead days, etc.) | Probability of stockout in horizon; depends on demand/interval/ETA + stock. |
| 10 | `excess_risk` | `LogisticRegression` / small boosted classifier on **simulated** stock/shelf-life trajectories | Probability of excess or spoilage given proposed order and forecast; depends on demand/ETA/stock/shelf life. |

## Important modeling integrity
- Outputs 01–07 trained on **generated** sales data and must be labeled synthetic, not externally validated. 08–10 on *separately simulated* supply/inventory outcomes, explicitly labeled `SIMULATED_SUPPLY`.
- For 09/10, generate outcomes in a physically consistent forward simulator using stock ledger, units sold, incoming arrivals, shelf-life rules; labels must come from simulation outcomes. Do not train target directly from the same risk formula you display while claiming real-world risk validation.
- Quantile predictions obey `0 <= p10 <= p50 <= p90` via explicit reconciliation and rounding; reconcile outputs after inference without falsifying reported raw model loss.
- If one agent fails, show actionable `unavailable` status, never silently fabricate its result. Optional fallback heuristics must be named fallback and source labeled.
- Each model must be **fitted**, serialized, loadable, invocable, and have at least one unit test. One artifact per agent (quantile agent may contain two estimators).
- Ensure scenario predictions react **meaningfully** to changing price, lead days, quantity and budget; don't return the same stored JSON for every scenario.

## CLI commands
`python -m app.cli train --all --threads 2` trains each sequentially; `python -m app.cli train --agent demand`; `python -m app.cli model-status` prints model list, versions, sizes and provenance. `--fast` trains smaller but functioning samples when practical.

## Tests and benchmarks
- Test loaded model round-trip gives stable output within tolerance.
- Different SKU/price/stock scenario produces nonidentical relevant results.
- Validate finite nonnegative forecasts, legal probabilities [0,1], and p10<=p50<=p90.
- All ten model artifacts and JSON metadata exist with meaningful metrics; use honest `Not available` where label/data too narrow.
- Capture actual training runtime per model, peak memory if measured, artifact file sizes. Do not claim model is better than baseline without comparative test.
