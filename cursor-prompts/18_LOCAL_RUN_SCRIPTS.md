# Phase 18 — Zero-cloud local bootstrap, run scripts, README

## Golden path
A new developer with Python 3.11/3.12, Node >=20, 8 GB RAM and 7 GB free should be able to run:
```
# terminal 1, project root
cd backend
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.cli bootstrap --products 200 --days 365 --seed 42 --threads 2
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# terminal 2, project root
cd frontend
npm install
npm run dev
```
`bootstrap` must **really** (1) migrate SQLite, (2) seed demo data if absent, (3) train all 10 artifacts one-by-one if absent/stale, (4) precompute cached 28-day forecast/risk summaries, (5) evaluate and persist metrics, (6) insert enough real traces/scenarios to populate pages from actual executed routines, (7) print status; safe to rerun without duplicating data. Provide `--force` only for explicitly confirmed destructive rebuilds and `--fast` for quick sanity checks.

## Automation scripts
- `scripts/setup.sh` / `setup.ps1`: check prerequisites, install dependencies and print next steps.
- `scripts/bootstrap.sh` / `bootstrap.ps1`: invoke local seed/train/evaluate (avoid redundantly reinstalling).
- `scripts/start-api.sh` / `.ps1`; `scripts/start-ui.sh` / `.ps1`: run servers in foreground in separate terminals with clear exit instructions.
- `scripts/verify.sh` / `.ps1`: execute back-end pytest, model-status, CLI evaluate where appropriate, frontend build, and HTTP check on running server (or launch API temporarily and shut down cleanly). Make scripts portable and report error exit codes.

## README must include
- Project intro and screenshot-inspired UI, explicitly `NO LLM`, ten-agent inventory intelligence.
- Prereqs (exact Python and Node versions tested, no GPU/cloud necessary).
- Local setup for Windows PowerShell and Linux/macOS, with exact path-sensitive commands and virtualenv instructions.
- Description of first-time bootstrap and approximate resource profile from **measured** run; state that actual duration may vary, no unverified promises.
- Main routes, API docs `http://127.0.0.1:8000/docs`, UI `http://localhost:5173`.
- Demo snapshot date and dataset is synthetic; how to reset and how not to delete data inadvertently.
- Ten agents table, DAG, ML evaluation and simulated labels distinction.
- Test commands, troubleshooting (`ModuleNotFoundError`, PowerShell execution policy, port in use, npm resolution, DB locked, disk low, missing artifacts), architecture & screenshots.
- AWS **future optional** note but no AWS dependency.

## Important practical constraints
Run Python and npm in separate processes. SQLite file is persistent; it is not an external database server. **Do not commit `stockpilot.db`, model jobs, node_modules or `.venv`.** No npm dev server required for API tests. If existing repo has files, integrate rather than overwrite user work.

## Acceptance
Actual clean local bootstrap completes; with frontend+backend running: `/api/health` succeeds and homepage loads, all 5 core pages work, data persists across API restarts. Record commands actually tested and the current memory/disk footprint in `docs/local-verification.md`.
