# API contract (local)

Base: `http://127.0.0.1:8000` · OpenAPI: `/docs`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | DB + model count, demo date |
| GET | `/api/dashboard` | KPIs (`inventory_value_paise`, `excess_inventory_value_paise`), forecast series, alerts, risk, recommendation |
| GET | `/api/inventory/summary` | catalog-wide SKU, low-stock, overstock, average days of supply, categories |
| GET | `/api/products` | page, page_size, search, category, supplier_id, risk, stock_health, sort, direction |
| GET | `/api/products/{id}` | detail + sales + forecast + movements |
| POST | `/api/products/{id}/adjust-stock` | `{delta, reason}` — rejects negative stock |
| GET | `/api/products/export.csv` | filtered CSV |
| GET | `/api/suppliers` | filter choices |
| GET | `/api/forecasts/{id}` | p10/p50/p90 series |
| POST | `/api/simulate` | what-if; no mutation; `SIMULATED_SUPPLY` |
| POST/GET | `/api/scenarios` | save / list |
| GET | `/api/scenarios/{id}` | stored inputs and results |
| POST | `/api/recommendations/{id}/propose` | draft reorder |
| GET | `/api/reorders` | list |
| GET | `/api/reorders/calendar` | arrivals, recommendations, and stockout watches with explicit date kinds |
| POST | `/api/reorders/{id}/approve\|reject\|receive` | receive adds stock once |
| GET | `/api/agents` | 10 cards; confidence null unless measured |
| GET | `/api/agent-runs` | trace summaries |
| GET | `/api/agent-runs/{trace_id}` | DAG nodes |
| POST | `/api/agent-runs/trigger` | `{product_id}` bounded on-demand run |
| GET | `/api/performance` | holdout metrics, simulated business block, stored agent step durations |
| GET | `/api/analytics/overview` | period KPIs, live stock, insights |
| GET | `/api/analytics/inventory-trend` | month-end inventory value |
| GET | `/api/analytics/turnover` | monthly turnover and DIO |
| GET | `/api/analytics/movements` | conserved unit and value waterfall |
| GET | `/api/analytics/top-products` | rankings by value, quantity, revenue, volume |
| GET | `/api/analytics/inventory-sales` | value, fulfilled revenue, ratio |
| GET | `/api/analytics/category-breakdown` | category value and sales |
| GET | `/api/analytics/abc-xyz` | statistical segmentation, paginated cell members |
| GET | `/api/analytics/slow-moving` | slow and excess proxies, no expiry |
| GET | `/api/analytics/suppliers` | catalog lead time plus simulated receipt stats |
| GET | `/api/analytics/filters` | years, categories, suppliers, products |

Shared analytics query: `from`, `to`, `year`, `month`, `category`, `supplier`, `product`. Invalid dates return 400. Unknown product or supplier returns 404. Formulas: [inventory-metrics.md](inventory-metrics.md).

Money fields are integer **paise**. Errors: 400 validation, 404 missing, 409 conflict, 503 model unavailable.
