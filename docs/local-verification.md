# Local verification evidence

**OS / tools:** Windows 10 (build 26200) · Python 3.12.9 · Node v24.x · npm 11.x  
**Date:** 2026-11-12 (post-repair)  
**Git baseline:** `c966aea` + repair changes (see `cursor-prompts/REPAIR_PROGRESS.md`)

## Repair verification (measured)

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q
# 36 passed

cd ..\frontend
npm run build
# tsc --noEmit && vite build OK

cd ..\backend
$env:OMP_NUM_THREADS=2
.\.venv\Scripts\python -m app.cli train --agent stockout_risk --fast
.\.venv\Scripts\python -m app.cli train --agent excess_risk --fast
.\.venv\Scripts\python -m app.cli evaluate
$env:PYTHONPATH="."
.\.venv\Scripts\python scripts\smoke_api.py
```

### Chronological holdout (rolling one-step) — after fix

| Method | WAPE | MAE | N |
|---|---|---|---|
| seasonal_naive_7 | ≈ 0.306 | ≈ 2.42 | 5600 |
| moving_average_28 | ≈ 0.291 | ≈ 2.30 | 5600 |
| demand_only | ≈ **0.290** | ≈ 2.29 | 5600 |

> Prior claim of demand WAPE ≈ 0.057 was **invalid** (single prediction vs mean holdout). Honest rolling one-step WAPE is ≈ 0.29, comparable to MA28.

- Backtest chart series: **28** daily aggregated points (200 SKUs)
- Interval empirical coverage (holdout): ≈ **0.832** (nominal ~80%)
- Evaluation mode: `rolling_one_step_holdout`

### Policy replay (SIMULATED, 5 SKUs, identical paths)

| Strategy | Mean defined cost (paise) | Mean stockout days |
|---|---|---|
| fixed_rule | ≈ 49,253 | 6.6 |
| demand_only | ≈ 23,716 | 3.4 |
| multi_agent | ≈ 18,349 | 2.4 |

Costs are holding + shortage penalties — **not** retail savings. Purchase cash is reported separately in eval JSON.

### Risk models

- Retrained with decision-time schema `decision_time_v1` (no future outcome features)
- Holdout Brier (fast retrain): stockout ≈ 0.025 · excess ≈ 0.025

## Bootstrap (existing demo DB preserved)

| Check | Result |
|---|---|
| Products | **200** |
| Sales rows | **73,000** |
| Agents | **10/10** artifacts |
| Demo date | 2026-11-01 |

Destructive reset was **not** run during repair. Risk agents were retrained in place; evaluate refreshed `artifacts/evaluation/`.

## API smoke (TestClient)

| Call | Result |
|---|---|
| GET `/api/health` | ok |
| GET `/api/dashboard` | ok |
| GET `/api/products` | ok |
| GET `/api/performance` | nonempty `backtest_series`, policy rows |
| GET `/api/agents` | ok |
| POST `/api/simulate` | applied_qty + price_effect + demand_p50 |
| POST adjust-stock | ok (reverted in smoke script) |

## Disk footprint (approx., unchanged order of magnitude)

| Path | Size |
|---|---|
| `backend/.venv` | ~355 MB |
| `frontend/node_modules` | ~105 MB |
| `backend/data/stockpilot.db` | ~8.2 MB |
| `backend/artifacts/models` | ~0.5 MB |
| `frontend/dist` | ~0.7 MB |

## Known limitations

- Unix scripts authored but **not** re-executed on Linux/macOS in this repair pass.
- p95 API latency remains **Not measured**.
- Price effects are **observational associations**, not causal elasticities.
- Multi-agent policy advantage above is on a **5-SKU SIMULATED** sample; not a guarantee of retail ROI.
- Full 200-SKU retrain of all agents not required after repair (risk schema change only); run `python -m app.cli train --all --fast` if artifacts look inconsistent.
- GitHub Actions CI workflow added as a file only (not pushed unless requested).
