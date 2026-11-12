# Phase 20 — Mandatory final integration, repair, and evidence

## Rule
This is not a review checklist to merely mark off: **run the application, measure outputs, fix defects, repeat**. Do not report "100% runnable" unless actual startup, API, and build verification succeeded in this workspace. State which OS you've verified; do not assert Windows tests if Linux-only.

## Checklist
- [ ] `mockup-ui/` untouched; all five screenshots mapped.
- [ ] `.venv` / npm deps installed under local disk budget; no AWS, Kaggle or GPU needed.
- [ ] `python -m app.cli bootstrap --products 200 --days 365 --seed 42 --threads 2` works on fresh or clean demo state.
- [ ] SQLite stores 200 products, 73,000 daily sales rows, suppliers, metrics, recommendations, actual agent traces.
- [ ] `python -m app.cli model-status` identifies 10 fitted ML agents with real artifact paths, versions and dataset provenance.
- [ ] `python -m app.cli evaluate` computes chronological holdout comparisons; no leakage warnings/failures.
- [ ] `python -m pytest` passes; test count and exact output in PROGRESS.
- [ ] `npm run build` passes; build output exists.
- [ ] FastAPI boots on 127.0.0.1:8000; `/api/health` and `/api/dashboard` return plausible JSON.
- [ ] Vite UI loads on localhost:5173 and main nav links work; no console/runtime errors noted.
- [ ] Command Center KPIs/chart and cards derive from API, not screenshot placeholders.
- [ ] Inventory list search/filter/sort/details + stock adjustment and CSV export work.
- [ ] Simulator sliders recompute metrics/path; save scenario + draft/approve/receive persist correctly.
- [ ] Agent Intelligence displays genuine ten fitted agents, DAG, trace details; no fake per-agent confidence.
- [ ] Performance shows measured backtests and correctly labeled simulated business metrics.
- [ ] 390px mobile and desktop layout inspected; no fatal overlap or impossible actions.
- [ ] README includes correct exact local startup commands for tested OS and clearly differentiates untested OS.
- [ ] No hardcoded dollar figures, fabricated business benefits, auth/production-security claims, unresolved broken buttons or placeholder TODO functions in core flow.

## Smoke walk-through
Start backend and frontend in separate terminal processes. With HTTP requests or browser automation tools already available (avoid installing heavy browser binaries): GET health → GET dashboard → GET products → GET one product → POST simulate(q=0) → POST simulate(q>0) → verify path difference → POST scenario save → create reorder draft → approve → receive → query inventory and assert delta exactly once → GET agents/traces → GET performance. Use a **throwaway test DB** for destructive smoke tests, not the demo DB the user might want to keep.

## Resource verification
Record measured peak RAM where tools permit, SQLite DB bytes, model artifact bytes, frontend node_modules + backend venv size, and total disk consumption. If target >7GB or memory thrashes, remediate (shrink samples, disable caches, reduce estimator size, trim packages) before completion. Do not delete user-created content.

## Final deliverables
Write `docs/local-verification.md` with actual commands, exit status, test count, models loaded, approximate artifact sizes, OS and versions, screenshots viewed, known limitations, evidence. Update `cursor-prompts/PROGRESS.md` with every phase status and any open issues. Final message to user should be compact and truthful: what was built, what checks passed, exact terminal startup, where to inspect it, and any limitations.

## If blocked by environment
If a tool cannot execute or package network unavailable, do not assert success. Implement and test everything possible, capture exact error, command and resolution steps in `PROGRESS.md`. Stop with an actionable report instead of pretending app is operational.
