# StockPilot Repair Progress

## Baseline (2026-11-12)

- **Git**: `master` @ `c966aea` (up to date with origin). Untracked initially: repair master prompt.
- **Environment**: Windows 10 | Python 3.12.9 | Node present | venv OK
- **Baseline pytest**: `14 passed, 3 warnings in 9.01s`
- **Prior PROGRESS.md**: Phases 02–20 marked complete with known-invalid WAPE ≈0.057 claim

### Confirmed bugs (pre-repair)

| ID | Issue | Pre-repair | Post-repair |
|---|---|---|---|
| A | Invalid demand holdout eval | PRESENT | **FIXED** — rolling 1-step, daily actuals |
| B | Risk feature leakage | PRESENT | **FIXED** — `decision_time_v1` schema |
| C | Optimizer candidate-independence + forced pack | PRESENT | **FIXED** — path costs + optional `risk_fn`; budget=0 → qty 0 |
| D | Price what-if disconnected | PRESENT | **FIXED** — price feats + observational delta |
| E | Flat forecast horizon | PRESENT | **IMPROVED** — mild DOW modulation of daily_p50 |
| F | Weak agent collaboration | PRESENT | **FIXED** — upstream signals condition demand; candidate risks in optimizer |
| G | Empty/incomplete performance | PRESENT | **FIXED** — series + coverage + policy replay |
| H | Sparse regression tests | PRESENT | **FIXED** — 36 tests |
| I | Stale state after adjust | PARTIAL (receive OK) | **FIXED** — risk/recs marked stale on adjust |

## Phase checklist

| Phase | Topic | Status | Evidence |
|---|---|---|---|
| 1 | Chronological backtesting | **DONE** | demand WAPE ≈0.290 (n=5600); series 28 pts; `test_backtest.py` |
| 2 | Risk classifiers no leakage | **DONE** | `sim_supply.py` decision-time only; `test_risk_leakage.py`; retrained |
| 3 | Optimizer & accounting | **DONE** | zero budget / pack / risk_fn tests |
| 4 | Multi-agent collaboration | **DONE** | `signal_flow` in orchestrator; `docs/agent-dependency-contract.md` |
| 5 | What-if simulator | **DONE** | price/lead/qty tests; applied_qty; observational label |
| 6 | Honest policy evaluation | **DONE** | policy replay rows; Performance UI cost labels |
| 7 | Data integrity | **DONE** | receive-once + stale-after-adjust tests |
| 8 | Frontend quality | **DONE** | Simulator applied qty + price note; Performance costs; `npm run build` OK |
| 9 | MLOps & docs | **DONE** | CI workflow file; checksum metadata; local-verification updated |

## Final measured results

```text
pytest: 36 passed
npm run build: OK
model-status: 10/10
evaluate demand_only WAPE: ~0.2896 (rolling_one_step_holdout, n=5600)
coverage empirical: ~0.832
policy replay multi_agent mean cost: ~18349 paise (5 SKUs) — lowest of three policies on this sample
API smoke: health/dashboard/products/performance/agents/simulate/adjust OK
```

### Key files changed

- `backend/app/ml/backtest.py`, `artifacts.py`
- `backend/app/agents/{sim_supply,stockout_risk,excess_risk,demand,price_response,calendar_effect,product_similarity}.py`
- `backend/app/services/{reorder_optimizer,scenarios,orchestrator,simulate_api,performance,policy_replay}.py`
- `backend/app/api/{routes,schemas}.py`, `backend/app/db/repositories.py`
- `backend/tests/test_{backtest,risk_leakage,optimizer,simulate_price,data_integrity,agent_signals,policy_replay}.py`
- `frontend/src/pages/{Simulator,Performance}.tsx`, `frontend/src/types/api.ts`
- `docs/{local-verification,agent-dependency-contract}.md`
- `.github/workflows/ci.yml`
- `backend/scripts/smoke_api.py`

### Commands for interviewer / resume

```powershell
cd "c:\D Drive\ML Master projects\StockPilot\backend"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m app.cli evaluate
$env:PYTHONPATH="."; .\.venv\Scripts\python scripts\smoke_api.py
cd ..\frontend; npm run build
.\scripts\start-api.ps1   # from repo root
.\scripts\start-ui.ps1
```

### Limitations / next optional work

- p95 latency still Not measured (need timed request sample).
- Price response remains observational, not causal.
- Multi-horizon recursive eval helper exists (`recursive_horizon_eval`) but primary reported metric is rolling 1-step.
- Unix scripts not re-verified on Linux/macOS.
- Do not push CI or commits unless requested.

## Continuation

All nine repair phases completed with measured evidence above. No remaining P0 blockers identified.
