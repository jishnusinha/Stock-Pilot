# Phase 08 — Actual multi-agent DAG, simulations and reorder optimization

## Build shared orchestration
Implement `app/agents/registry.py`, `app/services/orchestrator.py`, `app/services/scenarios.py`, `app/services/reorder_optimizer.py`, and `app/services/trace_writer.py`.

## DAG (explicit dependencies)
1. Base known state: selected SKU, sales history, known calendar/price, current stock, supplier, horizon, scenario inputs.
2. First layer: `calendar_effect`, `price_response`, `intermittence`, `sales_anomaly`, `product_similarity` (each independently consumes prepared features and data).
3. Forecast layer: `demand` consumes lag/calendar features + optionally adjusted price/calendar signals. `demand_interval` consumes aligned features and forecast.
4. Supply layer: `supplier_eta` uses supplier/order parameters.
5. Risk layer: `stockout_risk` and `excess_risk` consume forecast distribution, supplier ETA, stock level, SKU shelf life and the scenario's proposed reorder.
6. Final **deterministic optimizer** chooses reorder amount/due date under budget and pack-size constraints. This optimizer is NOT an eleventh trained ML agent; represent clearly as decision engine. `recommendation` is stored with trace ID and descriptive model inputs.

## Execution control
- Python simple topological scheduler with cached/lazy model loading. On 8 GB laptop, prefer sequential evaluation over concurrent 10 CPU-bound inference jobs. Compute commonly requested forecasts at bootstrap and cache by SKU+scenario hash+model version+snapshot date.
- `run_decision(product_id, scenario=None, persist_trace=True)` returns typed data plus structured summary. Need genuine trace of each agent call: wall-clock elapsed, model name, status, provenance, input/output summaries (bounded JSON), no fake per-agent confidence value.
- `run_type`: `forecast_batch`, `on_demand`, `what_if`, `backtest`; surface to frontend clearly.
- Preserve dependency correctness: risk reruns if price, stock, order quantity, ETA changes; caching keyed on ALL relevant scenario variables. Do not let hidden stale cache produce unchanged sliders.

## Scenario math (document precisely)
Compute a 28-day forward daily stock path: start from current stock; subtract simulated forecast/sampled demand; add reorder **only on expected arrival day**; optionally account for spoilage for perishable SKUs; clip fulfilled sales to available stock. Use fixed RNG seed for comparable baseline vs proposal uncertainty scenarios. Explain that this is forecast-based simulation, not observed future reality.

## Optimization objective
Try feasible pack-size multiples `q` from 0 to min(budget/cost, 300 or configurable cap), with limited candidates for speed. Minimize a documented weighted expected cost: purchase cash outlay (if relevant), holding cost, lost-sales penalty and spoilage/excess cost. Avoid conflating immediate purchase expenditure with net economic loss; show gross margin and budget explicitly. Derive order-by and arrival dates. If no feasible order, state so rather than recommend beyond budget.

## Explanations
Return structured reasons: `forecast_next_7_days`, `inventory_on_hand`, `lead_days`, `p_stockout_no_action`, `p_stockout_proposal`, `waste_risk`, `order_qty`, `budget`, `model_versions`, `provenance`. Generate a natural language summary **from templates**, no LLM needed. If probabilities come from training on simulation, label them `Simulated risk estimate`.

## Acceptance tests
- Higher proposed order quantity can't yield lower projected post-delivery stock *in the deterministic stock path* when all else held fixed.
- Lead time change alters arrival date and inventory path.
- Order approval does not magically alter physical inventory; only receiving goods does.
- Candidate quantity always pack-size multiple and within budget; zero order possible.
- Two identical decisions with same seed/state return equal outputs (excluding timestamps/latencies).
- Agent trace shows only actually invoked models, not a fake animated execution.
