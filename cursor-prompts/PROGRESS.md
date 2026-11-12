# StockPilot Progress

## Current status
- Current phase: **REPAIR COMPLETE** (see `REPAIR_PROGRESS.md`)
- Current state: local app runnable; ML correctness repairs applied
- Date / environment: 2026-11-12 | Windows 10 | Python 3.12.9 | Node v24.x
- Last passing commands: `pytest` **36 passed** · `npm run build` OK · `evaluate` OK · API smoke OK
- Honest holdout WAPE (demand_only, rolling 1-step): ≈ **0.290** (n=5600) — prior 0.057 claim retired
- Next action: (user) `.\scripts\start-api.ps1` and `.\scripts\start-ui.ps1`

## Repair phases (2026-11-12)
| Phase | Topic | Status |
|---|---|---|
| 1 | Chronological backtesting | DONE |
| 2 | Risk classifiers no leakage | DONE |
| 3 | Optimizer & accounting | DONE |
| 4 | Multi-agent collaboration | DONE |
| 5 | What-if simulator | DONE |
| 6 | Honest policy evaluation | DONE |
| 7 | Data integrity | DONE |
| 8 | Frontend fidelity | DONE |
| 9 | MLOps & docs | DONE |

## Original build phases 02–20
Previously completed (bootstrap, UI, etc.). Details retained historically; metrics superseded by repair evaluation where noted.
