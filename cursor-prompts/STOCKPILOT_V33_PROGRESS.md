# StockPilot 3.3 — Progress Tracker

**Started:** 2026-11-13  
**Base commit:** `7889eb882b551b752fd3957aa6e8607ce77d121a` (master)  
**Working tree at start:** clean  
**Status:** Implementation complete (not committed — awaiting user authorization)

## Hardware / disk (audit)

| Drive | Free GB (start) | Notes |
|-------|-----------------|-------|
| C: | ~12.4 | Available |
| D: (workspace) | ~1.13 | Tight — large CSVs gitignored |

## Baseline → final

| Check | Baseline | Final |
|-------|----------|-------|
| Backend pytest | 67 passed | **81 passed** |
| Frontend Vitest | 23 passed | **25 passed** |
| Frontend build | (prior pass) | **pass** |
| UCI download | n/a | **success** (SHA-256 recorded) |
| Real holdout WAPE (HGB) | n/a | **0.6611** |
| Seasonal naive WAPE | n/a | 0.9558 |
| Moving average WAPE | n/a | 0.8869 |
| Best method | n/a | hist_gradient_boosting |
| Synthetic models/DB | intact | intact |

## Phases completed

- [x] Phase 1 — Audit + progress file + baseline tests
- [x] Phase 2 — Official UCI download + SHA-256
- [x] Phase 3 — XLSX→CSV + data quality
- [x] Phase 4–6 — Daily sales, train-only SKU select (100), chronological splits
- [x] Phase 7–10 — Features, train HGB/quantiles/intermittence, baselines, reports
- [x] Phase 11 — `/api/real-data/*` read-only API
- [x] Phase 12 — Performance UI Synthetic / Real selector + RealRetailPanel
- [x] Phase 13 — Backend + frontend tests
- [x] Phase 14 — Local prepare/train/evaluate executed with real metrics
- [x] Phase 15 — Build verified; synthetic isolation preserved
- [x] Phase 16 — Docs: data README, dictionary, evaluation, interview guide, verification

## Key paths

**Backend:** `backend/app/real_data/*`, `backend/app/api/real_data_routes.py`, CLI `real-data-*`  
**Data:** `data/real/uci_online_retail/`  
**Experiments:** `experiments/real_data/uci_online_retail/`  
**Frontend:** `frontend/src/pages/Performance.tsx`, `features/performance/RealRetailPanel.tsx`  
**Docs:** `docs/real-data-evaluation.md`, `docs/real-data-interview-guide.md`, `docs/stockpilot-v33-verification.md`

## Commands

```powershell
cd backend
python -m app.cli real-data-all --max-products 100 --seed 42 --threads 2
python -m app.cli real-data-status
```

## Remaining

- User-authorized git commit/push only
- Optional: refresh returns reason counts after first-match cleaning tweak
- Optional: multi-horizon fixed-origin protocol
