# StockPilot Progress

## Current status
- Current phase: **20 COMPLETE**
- Current state: local app runnable end-to-end on Windows
- Date / environment: 2026-11-12 | Windows 10 | Python 3.12.9 | Node v24.19.0
- Resource measurements: venv ~355 MB · node_modules ~105 MB · DB ~8.2 MB · models ~0.42 MB
- Last passing commands: `pytest` 14 passed · `npm run build` OK · bootstrap 200×365 · API smoke OK
- Latest failure/blocker: none blocking; sklearn LogisticRegression convergence warnings (non-fatal)
- Next action: (user) run `.\scripts\start-api.ps1` and `.\scripts\start-ui.ps1`

## Phase status
| Phase | Topic | Status | Verified evidence |
|---|---|---|---|
| 02 | Product & mockups | DONE | `docs/mockup-map.md`, `docs/product-contract.md`; 5 PNGs inspected |
| 03 | Repo bootstrap | DONE | `backend/`, `frontend/`, `.gitignore`, scripts |
| 04 | SQLite schema | DONE | migrations + `test_db` |
| 05 | Data generation | DONE | 200×365 → 73,000 sales rows seed=42 |
| 06 | Features & splits | DONE | `test_features` lag/shift |
| 07 | Ten ML agents | DONE | 10 joblib artifacts; `model-status` |
| 08 | Orchestrator & optimizer | DONE | DAG + pack/budget optimizer; risk DOS rule |
| 09 | Backtesting | DONE | holdout WAPE demand_only≈0.057 vs baselines |
| 10 | Backend API | DONE | FastAPI routes + `test_api` |
| 11 | UI shell | DONE | AppShell/sidebar/tokens; `npm run build` |
| 12 | Command Center | DONE | `/` API-backed KPIs/chart/alerts |
| 13 | Inventory | DONE | filters, drawer, adjust, CSV |
| 14 | Simulator and reorders | DONE | simulate/scenarios + approve/receive |
| 15 | Agent UI | DONE | 10 agents, DAG, traces, trigger |
| 16 | Performance UI | DONE | measured metrics + SIMULATED business |
| 17 | QA & regression | DONE | **14 pytest passed**; frontend build |
| 18 | Local run scripts | DONE | setup/bootstrap/start/verify ps1+sh |
| 19 | Optional M5/docs | DONE | docs only (`optional-m5.md` + portfolio docs) |
| 20 | Final integration proof | DONE | `docs/local-verification.md` |

## Commands actually run (excerpt)
```powershell
python -m venv .venv
pip install --no-cache-dir -r requirements.txt
python -m app.cli bootstrap --products 50 --days 180 --seed 42 --threads 2 --fast   # early
python -m app.cli reset-demo --confirm
python -m app.cli bootstrap --products 200 --days 365 --seed 42 --threads 2 --fast
python scripts/refresh_risk.py   # after DOS-based risk classification
python -m pytest -q              # 14 passed
cd frontend; npm install; npm run build
uvicorn app.main:app --host 127.0.0.1 --port 8000
# HTTP smoke: health, dashboard, products, simulate, trigger, adjust-stock
```

## Mockup map
- `d6b91902-...png` → Command Center `/`
- `68b663be-...png` → Inventory `/inventory`
- `1457518b-...png` → Simulator `/simulator`
- `c0627307-...png` → Agents `/agents`
- `1c33fd0b-...png` → Performance `/performance`

## Resume steps
App is complete. To continue work: start API+UI per README; read `docs/local-verification.md` for measured baselines.
