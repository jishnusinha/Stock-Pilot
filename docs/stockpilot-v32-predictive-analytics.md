# StockPilot 3.2 — Predictive Inventory Analytics

Inventory Analytics now has three explicit layers:

| Layer | Source | UI tab |
|-------|--------|--------|
| Descriptive | Reconstructed snapshots (`inventory_*`) | Overview |
| Predictive | Persisted `forecasts` + `product_risk_cache` | Predictive Intelligence |
| Prescriptive | `recommendations` + `simulate_stock_path` | Decision Insights |

Design audit: [ml-analytics-integration-design.md](ml-analytics-integration-design.md).

## Architecture

```
sales / stock / suppliers
        │
        ▼
 existing 10 ML agents (train offline)
        │
        ▼
 forecasts · product_risk_cache · recommendations · agent_runs
        │
        ▼
 predictive_inventory_analytics.py
   + inventory_projection.py
        │
        ▼
 GET /api/analytics/predictive/*
        │
        ▼
 features/inventory-analytics/*  →  /analytics?tab=…
```

No eleventh ML model. GET handlers never train. Page loads read SQLite caches only.

## Data flow

1. **Cohort filters** (`category`, `supplier_id`, `product_id`, `segment`) select active products via the same helpers as historical analytics.
2. **Historical year/month** filters apply only to descriptive snapshot queries.
3. **Predictive as-of** is the forecast origin (`forecasts.as_of_date`, typically `2026-11-01`). It is shown in provenance UI and is never rewritten by a historical month filter.
4. Inventory projection starts from **live** `products.stock_on_hand`, not from a historical snapshot closing value.

## Model → visualization map

| Visualization | Primary sources |
|---------------|-----------------|
| Demand outlook | Demand Interval → `forecasts` (p10/p50/p90); sales history for actuals |
| Inventory value projection | Forecast p50 + `inventory_projection.project_inventory_path` |
| Stockout KPI / bands | `product_risk_cache.stockout_risk` (threshold ≥ 0.55) |
| Operational high risk note | `risk_level=high` (also short days-of-supply ≤ 7) |
| Excess value proxy | `forecast_28d` cover heuristic (45 days) — not Excess Risk Agent |
| Modeled excess risk | `recommendations.expected_excess_risk` |
| Replenishment table | Optimizer-backed `recommendations` |
| Explain / comparison | Trace `agent_runs` + no_reorder vs recommended paths |

Upstream agents (calendar, price, intermittence, anomaly, similarity) feed demand at decision time; they appear in traces, not as standalone charts.

## Forecast origins and horizons

- Origin: `forecasts.as_of_date`
- Horizon selector: **7 / 14 / 28** days
- 7- and 14-day totals = sum of the first N daily `p50_units` rows
- If fewer than N daily rows exist, that horizon is **unavailable** (not proportionally fabricated)
- Interval series persisted today is **flat across days** (Demand Interval); Demand Agent Dow-shaped `daily_p50` is not stored

## Inventory projection formula

For each future day:

```
opening = prior closing (day 0 = live stock)
available = opening + dated receipts
fulfilled = min(available, demand_p50)
unmet = demand_p50 − fulfilled
closing = available − fulfilled   # never < 0
closing_value = closing × unit_cost_paise
```

Modes:

| Mode | Receipts |
|------|----------|
| `no_reorder` | Pending/approved reorders with a stored `expected_arrival_date` only |
| `recommended` | Above + open recommendation `suggested_qty` on its predicted arrival |
| `scenario` | Explicit qty/lead for one product (simulator-linked) |

Arrival dates without a stored date are **not invented**.

## Uncertainty rules

- SKU p10–p90: Demand Interval Agent quantiles (nominal training target ≈ 80% coverage, **not** 95% confidence).
- Portfolio band: **sum of SKU quantiles** — labeled heuristic; not a calibrated joint quantile.
- Inventory paths are deterministic simulations; a demand interval is **not** automatically an inventory probability band.

## Risk aggregation

- Never sum stockout/excess probabilities.
- KPI “products at stockout risk” = count with `stockout_risk ≥ 0.55`.
- Separately report `operational_high_risk_level_count` from cache `risk_level`.
- Excess **value proxy** and modeled **excess_risk** are labeled distinctly.

## Freshness

| Status | Meaning |
|--------|---------|
| current | Forecast coverage complete; as-of matches demo date; no stale risk markers |
| partial | Some SKUs missing forecasts and/or stale risk after stock adjust |
| stale | Forecast as-of ≠ operational demo date |
| unavailable | No forecast rows |

Stock changes invalidate stockout cache / projections relevance; they do not by themselves invalidate demand forecasts.

## API endpoints

| Method | Path |
|--------|------|
| GET | `/api/analytics/predictive/overview` |
| GET | `/api/analytics/predictive/demand` |
| GET | `/api/analytics/predictive/inventory-projection` |
| GET | `/api/analytics/predictive/risks` |
| GET | `/api/analytics/predictive/recommendations` |
| GET | `/api/analytics/predictive/explain/{product_id}` |
| GET | `/api/analytics/predictive/data-quality` |

Query params: existing analytics filters + `horizon_days` ∈ {7,14,28}, `mode` ∈ {no_reorder,recommended,scenario}, optional scenario qty/lead/product.

## UI architecture

Route: `/analytics`

URL: `?tab=overview|predictive|decisions|quality&horizon=7|14|28&mode=no_reorder|recommended` (+ cohort filters)

Components live under `frontend/src/features/inventory-analytics/`.

Historical fetch key ignores horizon/mode. Predictive fetch key includes them.

## Known limitations

1. Flat daily interval forecasts in DB.
2. Portfolio uncertainty is a sum heuristic.
3. Few SKUs may exceed the 0.55 probability threshold even when many have `risk_level=high` from short cover.
4. Recommendation arrivals outside the selected horizon are skipped with a note.
5. No interactive model retrain from the analytics page.
