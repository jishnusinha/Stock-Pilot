# STOCKPILOT — Cursor Project Playbook

## What this is
This folder is a set of **execution instructions** for Cursor Agent to build a complete, locally runnable StockPilot inventory-intelligence web application. It is not the source code. The source code must be created in the **workspace root** (the parent of `cursor-prompts/`). Keep all these prompts intact for repeatability.

## Files that must already exist
- `mockup-ui/` — the five StockPilot UI screenshots saved by the user. Filenames can vary; find images recursively. If there are five, classify visually by: Command Center, Inventory Explorer, What-If Simulator, Agent Intelligence, Model Performance.
- `cursor-prompts/` — this folder.

## Non-negotiable success condition
The application must start **locally** with no AWS account, paid APIs, Kaggle authentication, GPU, Docker, Redis, or downloaded training dataset. An ordinary laptop (8 GB RAM, ~7 GB free disk) must be able to seed demo data, train lightweight models, start API/UI, and use every major screen. `README.md` must document verified commands for Windows PowerShell and Linux/macOS.

## How to run these prompts
1. Open the parent folder as Cursor workspace, switch to **Agent** mode, and paste the master kickoff prompt from `01_MASTER_KICKOFF.md` (or use the copyable version provided with this download).
2. Agent must execute `02` → `19` in filename order, reading each file completely just before implementing it. `00` and `01` are organizational instructions.
3. Maintain `cursor-prompts/PROGRESS.md` with current stage, completed tasks, tests/run command outcomes, blockers, and next step. It is a **generated progress file**, not a numbered specification.
4. After each stage run its acceptance checks, fix any failures, and checkpoint progress. Do not mark a phase done on implementation alone.
5. If the coding session reaches a context limit, preserve the state in PROGRESS.md so the next Agent session can resume; do not claim completion.

## Required implementation stack
- Frontend: React + TypeScript + Vite, React Router, Recharts, Lucide icons, custom CSS variables/CSS (keep dependencies lean).
- Backend: Python 3.11/3.12, FastAPI, Uvicorn, SQLite (`sqlite3`), Pandas, NumPy, scikit-learn, joblib, optional PyArrow for Parquet, Pytest and HTTPX for tests.
- ML: Ten small, **non-LLM** trained models grouped into modular Python agents; deterministic, dependency-aware orchestrator and transparent rule/optimization layer.
- Local-only dev: SQLite at `backend/data/stockpilot.db`, model files at `backend/artifacts/models/`, default seeded synthetic store data. No authentication system necessary for a **local** portfolio demo. Never expose unprotected endpoints to the public Internet as if production-secure.

## Core product behaviors
1. Command Center: derived KPIs, risk alerts, forecasts, actionable recommendations.
2. Inventory Explorer: search/filter/sort/pagination, product details, sales chart, stock editing with auditable movement, CSV export.
3. What-If Simulator: adjustable reorder qty / price / supplier lead time / budget, compare scenarios, chart derived from model and inventory calculations, save scenario, approval flow.
4. Agent Intelligence: real DAG, real agent list, real run traces, elapsed time, inputs/outputs/provenance and model status. Never pretend polling is live if predictions were precomputed.
5. Model Performance: real chronological backtests, baseline comparison, probabilistic evaluation where appropriate, simulation-based business outcomes clearly labeled.
6. Reorders: pending/approved/rejected recommendations, order records; real state mutations in SQLite, no fake purchase order transmission.

## Resource guardrails
- Start with 200 SKUs × 365 days (~73K daily rows); an optional `--days 540` mode is allowed after resource checks. Seed is reproducible. Training uses at most 2 threads by default and ONE model at a time.
- Prefer small estimator configurations (e.g. HistGradientBoosting with early stopping; small Ridge/ElasticNet; small IsolationForest; nearest-neighbor retrieval). Avoid TensorFlow/PyTorch and giant dependencies.
- Keep generated DB < 150 MB, all model artifacts < 200 MB, total workspace **new generated footprint** targeted < 2 GB (dependency downloads may vary). Never delete or modify `mockup-ui/`.
- Save model metadata, seed, train/test boundaries, and dataset provenance. All screenshots contain illustrative values; **do not hardcode those values into the production UI**.
- Fail with clear setup instructions rather than quietly substituting all model predictions with hardcoded constants. Graceful demo fixtures are fine **only** with explicit `DEMO / SIMULATED` labels.

## File execution order
See numbered files `02` through `19`. Do not skip evaluation, tests, or documentation. The pack deliberately includes mandatory run/repair phases.

## Final required proof
- Local backend and frontend start from clean instructions.
- `python -m pytest` passes and frontend `npm run build` passes.
- A seeded DB exists and contains the stated 200 SKU demo records.
- 10 model artifacts or formally documented agents with real fitted estimators, each with metadata and a callable inference contract.
- All five screenshot-derived pages display live data from the API and have functional interactions.
- No console errors / runtime exceptions in the smoke run, no broken main navigation links.
- No cloud account, network token, or external data needed **after installation of Python/npm packages**.
