# Local verification evidence

**OS / tools:** Windows 10 (build 26200) · Python 3.12.9 · Node v24.19.0 · npm 11.17.0  
**Date:** 2026-11-12  

## Bootstrap (measured)

```powershell
cd backend
.\.venv\Scripts\python -m app.cli reset-demo --confirm
$env:OMP_NUM_THREADS=2
.\.venv\Scripts\python -m app.cli bootstrap --products 200 --days 365 --seed 42 --threads 2 --fast
```

| Check | Result |
|---|---|
| Products | **200** |
| Sales rows | **73,000** |
| Suppliers | 8 |
| Agents trained | **10/10** status ok |
| Decisions cached | **200** |
| Holdout WAPE seasonal_naive_7 | ≈ 0.306 |
| Holdout WAPE moving_average_28 | ≈ 0.291 |
| Holdout WAPE demand_only | ≈ **0.057** (measured on SYNTHETIC_DEMO) |
| Simulated business sample | label `SIMULATED`, suggested cost 1,127,460 paise (5 SKUs) |
| Risk after DOS rule refresh | high **56**, medium **83**, nonzero recs **161** |

## Tests

```text
python -m pytest -q
14 passed
```

```text
npm run build
tsc + vite build OK (frontend/dist)
```

## API smoke (127.0.0.1:8000)

| Call | Result |
|---|---|
| GET `/api/health` | ok, db_ready, models_available=10 |
| GET `/api/dashboard` | KPIs, 84 forecast points, alerts, top risk, recommendation qty>0 |
| GET `/api/products` | total 200 |
| POST `/api/simulate` | q=0 vs q=48 changes ending inventory |
| POST `/api/agent-runs/trigger` | 10 nodes, ~3.2s |
| POST adjust-stock | persists |

## Disk footprint (approx.)

| Path | Size |
|---|---|
| `backend/.venv` | ~355 MB |
| `frontend/node_modules` | ~105 MB |
| `backend/data/stockpilot.db` | ~8.2 MB |
| `backend/artifacts/models` | ~0.42 MB |
| `frontend/dist` | ~0.66 MB |

## Known limitations

- Unix scripts authored but **not** executed on Linux/macOS in this workspace.
- `full_decision_system` WAPE intentionally N/A (business metrics under SIMULATED).
- p95 API latency shown as **Not measured**.
- Agent “confidence” not fabricated — UI shows N/A / omitted.
- `mockup-ui/` untouched; screenshot USD figures not hardcoded (INR paise).
- Optional M5 importer not required; see `docs/optional-m5.md`.
