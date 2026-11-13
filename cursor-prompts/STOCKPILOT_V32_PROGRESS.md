# StockPilot 3.2 — Progress Tracker

**Started:** 2026-11-13  
**Base commit:** `9defa41`  
**Status:** Implementation complete for core DoD; verification recorded

## Baseline → final

| Check | Baseline | Final |
|-------|----------|-------|
| Backend pytest | 54 passed | **67 passed** |
| Frontend Vitest | 13 passed | **23 passed** |
| Build | pass | pass |
| Forecast coverage | 200/200 | 200/200 (unchanged) |
| Models | 10/10 | 10/10 (no retrain) |

## Completed

- [x] Audit + `docs/ml-analytics-integration-design.md`
- [x] `inventory_projection.py` + conservation tests
- [x] `predictive_inventory_analytics.py` (overview, demand, projection, risks, recommendations, explain, data-quality)
- [x] FastAPI routes under `/api/analytics/predictive/*`
- [x] Frontend workspace tabs + `features/inventory-analytics/*`
- [x] Cross-filter + forecast-as-of provenance; historical month ≠ predictive origin
- [x] Deferred historical fetch when on predictive/decisions tabs (8GB-friendly)
- [x] Docs: predictive analytics + verification; README + progress updated

## Key files

**Backend:** `app/services/predictive_inventory_analytics.py`, `inventory_projection.py`, `api/analytics_routes.py`, `tests/test_predictive_inventory_analytics.py`, `tests/test_inventory_projection.py`

**Frontend:** `pages/InventoryAnalytics.tsx`, `features/inventory-analytics/*`, `utils/analyticsQuery.ts`, `api/client.ts`, `types/api.ts`

**Docs:** `docs/ml-analytics-integration-design.md`, `docs/stockpilot-v32-predictive-analytics.md`, `docs/stockpilot-v32-verification.md`

## Remaining optional polish

- Broader responsive screenshot matrix (768/390) and dark-theme visual pass
- Round-trip browser automation for product Explain → comparison chart
- Commit when requested (not done)

## Blockers

None for core demo path. Under heavy parallel historical load, overview can exceed 40s — mitigated by tab-deferred fetching.
