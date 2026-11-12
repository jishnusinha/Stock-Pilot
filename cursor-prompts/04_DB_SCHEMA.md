# Phase 04 — SQLite schema, repositories and safe database access

## Principle
One local SQLite database. All schema operations idempotent. Money as integer `*_paise`; UTC timestamps ISO 8601; demo dates as YYYY-MM-DD. Enforce `PRAGMA foreign_keys=ON`, set `busy_timeout`, use transactions for mutations, parameterized SQL, indices on product/date and status, and use one connection per request or explicit transaction context. SQLite WAL may be enabled locally. No cloud DB.

## Required tables
- `schema_migrations(version, applied_at)`
- `suppliers(id, name, base_lead_days, delivery_reliability, created_at)`
- `products(id, sku UNIQUE, name, category, supplier_id FK, unit_cost_paise, selling_price_paise, stock_on_hand, reorder_point, pack_size, shelf_life_days NULLABLE, is_active)`
- `sales(id, product_id FK, sale_date, units, selling_price_paise, promo_flag, event_flag, UNIQUE(product_id,sale_date))`
- `inventory_movements(id, product_id FK, delta_units, reason, reference, created_at)`
- `forecasts(id, product_id FK, as_of_date, target_date, p10_units, p50_units, p90_units, model_version, provenance, UNIQUE(product_id,as_of_date,target_date,model_version))`
- `recommendations(id, product_id FK, created_at, suggested_qty, expected_stockout_risk, expected_excess_risk, estimated_cost_paise, expected_arrival_date, explanation_json, status, trace_id)`
- `reorders(id, product_id FK, recommendation_id NULLABLE FK, qty, unit_cost_paise, status, created_at, reviewed_at NULLABLE, notes)`
- `scenario_runs(id, product_id FK, created_at, input_json, result_json, provenance)`
- `agent_runs(id, trace_id, agent_name, started_at, duration_ms, status, model_version, provenance, input_summary_json, output_summary_json, error_text NULLABLE)`
- `model_metrics(id, agent_name, version, metric_name, metric_value, evaluation_split, dataset_source, computed_at)`
- `model_versions(id, agent_name, version, artifact_file, training_source, train_start, train_end, test_start, test_end, trained_at, metadata_json)`

## Constraints
Stock cannot become negative by manual adjustment; invalid unit costs/prices or qty rejected; supplier FK enforced. No duplicate daily sales. Only approved reorders can impact inventory and **do not** instantly add goods: on approval status goes `approved`; optional `received` action adds units to inventory via a movement. Rejected orders have no effect. Under no circumstance represent approved order as externally placed with a real supplier.

## Services
Build `app/db/connection.py`, `migrations.py`, repository functions for product list/search/filter/page, sales range, products summary, inventory adjustment, recommendations, scenario save, reorder status, agent traces and model metrics. Keep SQL outside route bodies and use type-checked Pydantic schemas at boundary. Demonstrate transaction rollback and FK enforcement with tests.

## Tests / proof
- Fresh bootstrap creates all tables and indices twice without duplication/error.
- Insert/select product works; stock adjustment persists after reopening connection.
- Invalid stock edit fails cleanly and rolls back.
- Approved order is not counted as received stock until explicit receive.
- Foreign key violation is rejected.
- DB file generated only under configured data path.
