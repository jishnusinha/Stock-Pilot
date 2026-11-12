# Phase 17 — Automated tests, safety, regression, cross-layer correctness

## Required backend pytest modules
- `test_db.py`: migrations/rollback/FK/stock movements and receipt idempotency.
- `test_seed.py`: row counts/reproducibility/canonical checksum.
- `test_features.py`: shifted lags, no holdout leakage, consistent mapping train-vs-infer.
- `test_agents.py`: all ten model artifacts load/infer; shape/finite/probability checks; real changes for changed inputs.
- `test_orchestrator.py`: DAG dependencies and call traces, stable scenario caching, invalidation and idempotency.
- `test_optimizer.py`: budget and pack constraints, inventory arrival timing, zero demand and no feasible reorder.
- `test_api.py`: health, dashboard, product CRUD-ish adjustment, filtered results, scenario, reorders lifecycle, trace, performance.

## Frontend checks
- `npm run build` typecheck.
- Add a light smoke mechanism if affordable (Vite build output and browser manual checklist); do not install gigabytes of browser binaries on the 7 GB machine unless already available.
- Check network responses via curl/Python HTTPX and review runtime console/terminal logs; no continuous failed API polling, missing keys or broken images.

## Security and data correctness
- Parameterized SQL only; validate/sanitize CSV export; no exposed SQLite path or stacktrace in API; CORS restricted to local frontend.
- Local demo no login; explicitly note that public AWS deployment would require auth, HTTPS, rate limiting, secrets, tenancy and network protection. Do not suggest opening unprotected FastAPI port publicly.
- Backend `/api/agent-runs/trigger` only accepts bounded SKU inputs and predeclared agent mode, cannot execute arbitrary code or load user-specified paths.
- CSV import optional later: never allow arbitrary uploaded filenames to overwrite app files. Current version no CSV upload required.
- Approve/receive reorders exactly once; protect against duplicate button presses and double inventory credit.
- Handle offline/no-internet after deps installed, model missing, malformed query, zero demand, filters with no results, non-finite ML output, and different OS path separators.

## Definition of passing
Run `python -m pytest` from backend; zero failures. Run `npm run build`; zero TS/build failures. Run `python -m app.cli model-status` and `evaluate` with no missing data; log actual outputs and fixes in PROGRESS. No "tests skipped" unless clearly explained and not core acceptance tests.
