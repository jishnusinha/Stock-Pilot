# Phase 10 — FastAPI: typed and tested contract for every page

## Endpoints
All JSON under `/api`; use Pydantic schemas, service layer, pagination and clear errors. Each endpoint returns its own `data_source` or `provenance` where predictions/savings are involved.

| Method | Path | Core responsibility |
|---|---|---|
| GET | `/api/health` | `status`, DB readiness, 10-model availability, demo date, version |
| GET | `/api/dashboard` | KPI totals, forecast chart, 3 critical alerts, top risk SKUs, a recommended action; all derived from DB/model output |
| GET | `/api/products` | page,page_size,search,category,supplier_id,risk,sort; total and rows |
| GET | `/api/products/{id}` | product, supplier, historical sales, forecast, movements, risk/reorder |
| POST | `/api/products/{id}/adjust-stock` | reason + signed delta; durable movement, validation |
| GET | `/api/suppliers` | supplier choices for filters |
| GET | `/api/forecasts/{product_id}` | 28-day p10/p50/p90 series and as-of date |
| POST | `/api/simulate` | SKU + reorder qty, proposed price, lead days, budget; returns both baseline and proposed time series + derived metrics; no mutation |
| POST | `/api/scenarios` | save named scenario and exact inputs/results |
| GET | `/api/scenarios` | saved scenario history |
| POST | `/api/recommendations/{id}/propose` | create a draft reorder tied to recommendation |
| GET | `/api/reorders` | pending, approved, rejected, received orders |
| POST | `/api/reorders/{id}/approve` | approve draft, no inventory stock mutation yet |
| POST | `/api/reorders/{id}/reject` | reject draft, persisted |
| POST | `/api/reorders/{id}/receive` | receive approved order, durable positive inventory movement |
| GET | `/api/agents` | all 10 model cards + metadata/availability |
| GET | `/api/agent-runs` | real run trace summaries, filter and paginate |
| GET | `/api/agent-runs/{trace_id}` | DAG/individual node details, timing, provenance |
| POST | `/api/agent-runs/trigger` | trigger real small on-demand inference for selected SKU; rate-limited/local demo, not arbitrary remote code |
| GET | `/api/performance` | DB-backed measured metrics, baseline comparisons, versions, evaluation source disclosures |
| GET | `/api/products/export.csv` | filtered product rows as stream, safe CSV fields |

## API details
- Design route names and request/response TS interfaces once; write `docs/api-contract.md` with examples from actual responses. If an identifier scheme must change, update both sides and tests.
- Product table risk should reflect stock and latest forecasts, with explicit stale timestamp. No N+1 per row inference; precompute risk at bootstrap or aggregate in SQL.
- `GET /api/dashboard` should not retrain models or execute expensive 200-SKU forecasting in request path. The CLI bootstrap precomputes.
- CORS allow localhost:5173 and 127.0.0.1:5173; configure port 8000. No wildcard CORS with credentials.
- Explicit business validation for price/qty/lead/budget, cap scenario workload, descriptive HTTP 400/404/409/422 responses. Unavailable model should generate explanatory 503 or degraded status, not fake output.
- `GET /api/health` should not expose local path, hidden credentials, or raw stack traces.

## Tests
Use `TestClient` with isolated temp SQLite and tiny fitted demo artifacts. Include scenario contract, product filters, adjustment/rollback, reorder approval-receipt, missing SKU, unknown trace, and API error handling. The test suite must not accidentally write into normal user data or require internet.
