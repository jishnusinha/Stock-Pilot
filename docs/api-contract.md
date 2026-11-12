# API contract (local)

Base: `http://127.0.0.1:8000` · OpenAPI: `/docs`

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | DB + model count, demo date |
| GET | `/api/dashboard` | KPIs, forecast series, alerts, risk, recommendation |
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
| POST | `/api/reorders/{id}/approve\|reject\|receive` | receive adds stock once |
| GET | `/api/agents` | 10 cards; confidence null unless measured |
| GET | `/api/agent-runs` | trace summaries |
| GET | `/api/agent-runs/{trace_id}` | DAG nodes |
| POST | `/api/agent-runs/trigger` | `{product_id}` bounded on-demand run |
| GET | `/api/performance` | holdout metrics + simulated business block |

Money fields are integer **paise**. Errors: 400 validation, 404 missing, 409 conflict, 503 model unavailable.
