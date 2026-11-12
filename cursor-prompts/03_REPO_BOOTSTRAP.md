# Phase 03 — Repository, environments, configuration

## Create
```
stockpilot/
  mockup-ui/                  # user-owned; never rewrite
  cursor-prompts/             # user-owned instructions
  docs/
  backend/
    app/{api,agents,core,db,ml,services}/
    scripts/
    tests/
    data/                     # runtime only, gitignored
    artifacts/models/         # runtime only, gitignored
    requirements.txt
  frontend/
    src/{api,components,pages,styles,types,utils}/
    public/
  scripts/
  .gitignore
  README.md
```
Do not put nested `stockpilot/` inside the root. Create `__init__.py` in importable Python packages.

## Requirements
- Python 3.11 or 3.12, Node.js >=20 recommended. Check installed versions; if incompatible, document actionable instructions and use smallest compatible version. Avoid a forced system upgrade.
- Backend packages: FastAPI, uvicorn, pandas, numpy, scikit-learn, joblib, pydantic, pytest, httpx, optional pyarrow (if omitted use CSV/SQLite). Pin a tested compatible range or lock versions after successful install; do not pin nonexistent versions.
- Frontend packages: `react`, `react-dom`, `typescript`, `vite`, `react-router-dom`, `recharts`, `lucide-react`, `@types/react`, `@types/react-dom`; only add extras where demonstrably needed.
- Avoid Next.js, TensorFlow, PyTorch, Spark, MLflow server, Celery, Docker, Redis, Postgres, large UI libraries, or direct AWS SDK dependency.

## Configuration
- `backend/app/core/config.py`: `STOCKPILOT_DB_PATH` (default absolute derived `backend/data/stockpilot.db`), `STOCKPILOT_MODEL_DIR`, `STOCKPILOT_DEMO_DATE` (default 2026-11-01), `STOCKPILOT_SEED` (42), `STOCKPILOT_THREADS` (2), `STOCKPILOT_DEMO_MODE` (true). Use `pathlib` for portable paths.
- `frontend/.env.example`: `VITE_API_URL=http://127.0.0.1:8000`; use local Vite proxy if more convenient. Never commit secrets.
- `.gitignore`: Python venv/cache, node_modules, SQLite DB/WAL/SHM, artifacts/*.joblib, generated raw data, dist, .env, test caches. Do not gitignore `mockup-ui/` without asking; user's assets are references.
- `docs/architecture.md`: simple local diagram UI → FastAPI → SQLite + lazy sklearn models.
- Use one backend API process and one frontend dev server. No external database process.

## Working setup commands
Create equivalent `scripts/setup.sh` and `scripts/setup.ps1` that create backend `.venv` and install deps, then install frontend deps. Scripts should stop on error and never remove user files. Create `scripts/start-api.sh/.ps1`, `scripts/start-ui.sh/.ps1`, and `scripts/verify.sh/.ps1` as later phases progress. Test PowerShell syntax if Windows available; otherwise state not verified.

## Checks
- Python import of `fastapi`, `sklearn`, `pandas` from backend venv works.
- `npm install` and an initial placeholder Vite build work.
- `python -c "import sqlite3; print(sqlite3.sqlite_version)"` succeeds.
- Document measured disk footprint after setup. Do not include generated files in git.
