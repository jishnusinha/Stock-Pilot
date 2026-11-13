# StockPilot 3.2 — Verification Report

**Date:** 2026-11-13  
**Base commit:** `9defa41`  
**Workspace:** local master with StockPilot 3.2 predictive analytics changes (uncommitted)

## Baseline (pre-change)

| Check | Result |
|-------|--------|
| Backend pytest | 54 passed |
| Frontend Vitest | 13 passed |
| `tsc` + Vite build | pass |
| SQLite integrity | `ok` |
| Forecast coverage | 200/200 SKUs, as_of `2026-11-01`, model `1.0.0` |
| Model artifacts | 10/10 joblib agents present |
| Open recommendations | 198 |

## Post-change automated tests

| Check | Result |
|-------|--------|
| Backend pytest | **67 passed** (was 54; +13 projection/predictive tests) |
| Frontend Vitest | **23 passed** (was 13) |
| `npm run build` | **pass** (`tsc --noEmit` + Vite) |

## Live API checks (demo DB)

| Endpoint | Sample result |
|----------|---------------|
| `GET /api/analytics/predictive/overview?horizon_days=28` | `ready=true`, demand≈44811, at_risk(prob≥55%)=3, ops high risk_level=58, coverage 200/200, freshness `partial` (1 stale risk row) |
| `GET .../inventory-projection?mode=no_reorder` | ending value ≈ ₹1.70L (paise 17052636) |
| `GET .../risks` | distribution + excess proxy/modeled split |
| `GET .../recommendations` | ranked optimizer rows |

### Latency (single-client, lightly loaded)

| Call | ms |
|------|-----|
| predictive overview | ~870 |
| inventory projection | ~200 |
| risks | ~525 |
| recommendations | ~524 |
| demand (14d) | ~480 |

**Note:** Under parallel load with all 11 historical analytics endpoints, overview latency rose to ~48s on this 8GB host. The UI now **defers heavy historical fetches** until Overview/Quality tabs so predictive tabs stay responsive.

## Browser checks

| View | Result |
|------|--------|
| `/analytics` Overview | Historical KPIs, charts, ABC–XYZ, suppliers load |
| `/analytics?tab=predictive` | Provenance (as-of 2026-11-01, model 1.0.0), KPI strip with real demand/risk/excess/coverage, demand + projection charts |
| `/analytics?tab=decisions` | Recommendation table with Simulator/Agents/Explain actions; ML insights; comparison placeholder until product explain |
| Command Center | Unaffected; models 10/10 |
| Light theme | Verified |
| Dark theme | Not exhaustively re-shot this session; CSS variables reused |

Viewport automation used 1440 CSS px after clearing a cramped embedded browser viewport. Full multi-breakpoint screenshot matrix was not completed in this pass.

## Features preserved

- Historical reconstruction analytics and formulas unchanged
- Ten trained agents + artifacts untouched (no retrain on GET)
- Reorder approve/receive semantics unchanged
- Forecasts continue to come from Demand Interval → `forecasts` table
- Optimizer recommendations drive Decision Insights

## Known limitations (honest)

1. Portfolio p10–p90 is a **sum-of-SKU heuristic**, not a joint quantile.
2. Persisted interval series is **flat** across days.
3. Probability-threshold stockout KPI (3 SKUs ≥55%) differs from cache `risk_level=high` (58), which also flags short days-of-supply — both are shown.
4. Freshness can be `partial` when any risk row carries `STALE_AFTER_STOCK_ADJUST`.
5. On constrained RAM, avoid opening Overview and Predictive under heavy concurrent API load without the tab-deferred fetch behavior.

## Definition of Done mapping (summary)

Predictive service, projection conservation tests, typed endpoints, tabbed UI, provenance, filters, optimizer recommendations, docs, and automated tests are complete. Browser checks covered primary tabs with live ML outputs. Remaining polish: broader responsive screenshot matrix and dark-theme visual pass.
