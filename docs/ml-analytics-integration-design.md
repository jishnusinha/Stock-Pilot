# StockPilot 3.2 — ML Analytics Integration Design

**Audited commit / tree:** `9defa41` (local master, clean at start)  
**Date:** 2026-11-13

This document maps real ML agent outputs to Inventory Analytics visualizations. Column names and semantics were read from `backend/app/db/migrations.py`, `orchestrator.py`, agents, and repositories — not invented.

---

## Three data layers

| Layer | Source of truth | May be labeled ML? |
|-------|-----------------|--------------------|
| **Descriptive** | `inventory_daily_snapshots`, ledger, sales | No — reconstructed / observed |
| **Predictive** | `forecasts`, `product_risk_cache`, agent traces | Yes — when rows exist |
| **Prescriptive** | `recommendations` + `optimize_reorder` + `simulate_stock_path` | Decision support; not a new model |

Historical year/month filters control the descriptive layer only. Predictive charts use the forecast **as_of_date** (typically `settings.demo_date` = `2026-11-01`).

---

## Ten-agent output matrix

| Agent | Algorithm | Storage | Key outputs | Date basis | Horizon | Model version | API | Aggregate-safe? | Can stale? | Safe for predictive viz? |
|-------|-----------|---------|-------------|------------|---------|---------------|-----|-----------------|------------|--------------------------|
| Calendar Effects | Ridge | joblib + `agent_runs` | `calendar_uplift` | as-of / last sale | n/a | artifact / run | trace | No | Trace-only | Upstream signal only |
| Price Response | Ridge / ElasticNet | joblib + runs | `expected_units_delta` | current price | n/a | artifact / run | `/simulate`, trace | No | Trace-only | Observational; label clearly |
| Intermittent Demand | LogisticRegression | joblib + runs | `p_zero_demand`, `is_intermittent` | last feature row | n/a | artifact / run | trace | No | Trace-only | Feature flag |
| Sales Anomaly | IsolationForest | joblib + runs | `is_anomaly`, `anomaly_score` | last feature row | n/a | artifact / run | trace | No | Trace-only | Flag only |
| Product Similarity | NearestNeighbors | joblib + runs | `similarity_demand`, `neighbors` | last 28d sales | n/a | artifact / run | trace | **No** | Trace-only | Sparse assist only |
| Demand Forecast | HistGradientBoostingRegressor | joblib + runs | `p50_units`, `daily_p50` (28) | last sale in features | 28d shape in memory | artifact / run | `/simulate`, decision | Sum of expected units OK | Until re-decision | **daily_p50 not in DB** |
| Demand Interval | Quantile GBR | joblib + **`forecasts`** + runs | `p10/p50/p90_units` per day | `as_of_date`, `target_date` | **28 daily rows** | `forecasts.model_version` | `GET /forecasts/{id}`, dashboard | Sum = expected **total** units; **not** a joint quantile | Until replace for as_of/version | **Primary demand chart source** |
| Supplier ETA | RandomForestRegressor | joblib + runs | `eta_days`, `lead_days` | supplier/product | n/a | artifact / run | decision arrival | No | Trace-only | Lead-time display |
| Stockout Risk | HistGB Classifier | joblib + **`product_risk_cache`** + recommendations | `stockout_risk` | decision-time features | 28d training label | runs / cache time | products, dashboard | **Never sum probabilities** | Yes (stock adjust) | SKU probability + counts |
| Excess Inventory Risk | HistGB Classifier | joblib + **`recommendations.expected_excess_risk`** | `excess_risk` | decision-time | 28d training label | runs | recommendations / simulate | Never sum probs | Recs mark stale | Separate from excess **value proxy** |

**Deterministic optimizer** (`reorder_optimizer.optimize_reorder`): not an ML agent. Writes suggested qty / cost into recommendations via bootstrap / refresh / trigger.

---

## Persistence contracts

### `forecasts`
- One row per `(product_id, as_of_date, target_date, model_version)`
- Columns: `p10_units`, `p50_units`, `p90_units`, `provenance`
- Written by `run_decision` → `replace_forecasts` from Demand Interval `forecast_series`
- Interval series is **flat across days** (same quantiles repeated); Demand Agent Dow-shaped `daily_p50` is **not** persisted

### `product_risk_cache`
- One row per product: `risk_level`, `days_of_supply`, `forecast_28d` (= `p50 * 28`), `sell_through`, `stockout_risk`, `updated_at`, `provenance`
- **No `excess_risk` column**
- Stock adjust may append `STALE_AFTER_STOCK_ADJUST` to provenance

### `recommendations`
- `suggested_qty`, `expected_stockout_risk`, `expected_excess_risk`, `estimated_cost_paise`, `expected_arrival_date`, `explanation_json`, `status`, `trace_id`

### Artifacts
- `backend/artifacts/models/{agent_name}/{version}.joblib`
- Registry: `model_versions`

---

## Feature → model mapping

| UI feature | Agents / engines | Storage used |
|------------|------------------|--------------|
| Demand outlook (7/14/28) | Demand Interval (+ Demand upstream) | `forecasts` daily rows |
| Forecast uncertainty band | Demand Interval | SKU p10–p90; portfolio = labeled sum heuristic |
| Inventory value projection | Interval forecasts + stock simulation | live `stock_on_hand` + unit cost + receipts |
| Stockout exposure | Stockout Risk (+ ETA, Demand) | `product_risk_cache.stockout_risk` |
| Excess value proxy | Demand cache | `forecast_28d` cover heuristic (45 days) — **not** Excess Risk Agent |
| Modeled excess risk | Excess Risk | `recommendations.expected_excess_risk` |
| Replenishment spend / qty | Optimizer | `recommendations` |
| Scenario compare | `simulate_stock_path` / What-If | recommendations or scenario inputs |
| Explain / traces | Orchestrator | `agent_runs` by `trace_id` |
| Historical KPIs | none (deterministic) | snapshots |

Agents that do **not** drive a dedicated chart: calendar, price, intermittence, anomaly, similarity — they feed Demand or appear in traces.

---

## Inventory projection formula

For each future day `t` and SKU:

```
opening = previous closing (or live stock on day 0)
receipts = approved/predicted arrivals on t (only when a stored date exists)
available = opening + receipts
fulfilled = min(available, predicted_demand_p50[t])
unmet = predicted_demand_p50[t] - fulfilled
closing = available - fulfilled   # never < 0
closing_value = closing * unit_cost_paise
```

Modes:
1. **no_reorder** — existing approved reorder arrivals only when `expected_arrival_date` is stored; no new PO
2. **recommended** — add open recommendation `suggested_qty` on its `expected_arrival_date` (predicted label)
3. **scenario** — explicit user qty / lead from simulator inputs

---

## Aggregation & uncertainty rules

1. Portfolio expected demand = **sum of SKU p50** (linear expectation under additivity of means).
2. Portfolio p10/p90 shown only as **“sum of SKU quantiles (heuristic; not a calibrated joint quantile)”**.
3. Do **not** sum stockout/excess probabilities; report **counts** and distributions.
4. Incomplete calendar months in historical charts: expose `days` and mark **partial month**.
5. November terminal reconciliation is **descriptive reconstruction**, not a forecast.

---

## Freshness policy

| Signal | Fresh when | Stale when |
|--------|------------|------------|
| Demand forecast | Latest `as_of_date` matches active demo as-of; rows present | Missing coverage; superseded model_version with empty replace |
| Stockout cache | Provenance without `STALE_AFTER_STOCK_ADJUST`; `updated_at` present | Stock adjusted after cache; provenance stale marker |
| Excess risk on rec | Recommendation `open`/`proposed` and not status `stale` | `status='stale'` after stock adjust |
| Inventory projection | Uses **live** stock + current forecasts | Forecast missing → unavailable path; stale risk flagged separately |

GET endpoints **never** retrain. Refresh = existing `run_decision` / `refresh_risk` workflows only.

---

## Planned API surface

| Method | Path | Role |
|--------|------|------|
| GET | `/api/analytics/predictive/overview` | KPI strip + provenance |
| GET | `/api/analytics/predictive/demand` | Historical sales + forecast series |
| GET | `/api/analytics/predictive/inventory-projection` | Paths by mode/horizon |
| GET | `/api/analytics/predictive/risks` | Stockout distribution + ranking |
| GET | `/api/analytics/predictive/recommendations` | Optimizer-backed opportunities |
| GET | `/api/analytics/predictive/explain/{product_id}` | Signals + optional trace |

Filters reuse analytics cohort: `category`, `supplier_id`, `product_id`, `segment`, plus `horizon_days` ∈ {7,14,28} and `mode`.

---

## UI architecture

Tabbed workspace on `/analytics`:

**Overview | Predictive Intelligence | Decision Insights | Data Quality**

Shared filter bar + URL `tab` param. Historical month does not rewrite predictive as-of labels.

Component home: `frontend/src/features/inventory-analytics/`.
