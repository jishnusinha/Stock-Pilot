# MASTER KICKOFF PROMPT — StockPilot

> This is a copyable instruction intended to be pasted into **Cursor Agent chat** while the project root is open. Keep reading after this file: the work is defined by the rest of this folder.

You are the lead full-stack engineer, ML engineer, data engineer, QA engineer, and product designer for **StockPilot**. Build the entire application in this workspace, not just a plan. The project root contains `mockup-ui/` with five reference screenshots and `cursor-prompts/` with your detailed sequential implementation specifications.

First inspect the actual workspace and the five UI images. Read `cursor-prompts/00_START_HERE.md`, `cursor-prompts/02_PRODUCT_SPEC.md`, and the remaining numbered files **in order**, implementing each phase and verifying its acceptance criteria before moving on. The prompts are source-of-truth for features and data contracts; mockups are source-of-truth for layout, hierarchy and visual language. Resolve inconsistencies by choosing correct, functional behavior over visually fabricated numbers. Never change the mockup files.

**Operating constraints:** laptop 8 GB RAM, ~7 GB free space, CPU only; AWS not needed for local success. Use React + TypeScript + Vite + Recharts + Lucide + light custom CSS, Python FastAPI + SQLite + scikit-learn. No LLMs, external API keys, Kaggle login, Docker, Redis, Kubernetes, cloud services, heavy ML frameworks, giant datasets, or fake success metrics. Seed a deterministic synthetic retail dataset locally (200 SKUs × 365 days), fit ten compact NON-LLM ML agents with honest simulated-vs-historical labels, implement a dependency-aware agent orchestration graph, derived forecasts, a genuine reorder optimizer, and measured backtests.

**Execution rules:**
1. Make and persist a checklist in `cursor-prompts/PROGRESS.md` immediately. Record timestamps, phases, commands actually run, results, errors, next stage. When a check fails, debug it, rerun, and only then continue.
2. Implement all numbered phases `02`–`19` sequentially, using each MD for detailed acceptance criteria. Use your terminal and editor tools to write real source files, install dependencies, run migrations/seeding/training, launch and test the app, and iterate on defects. Do not stop at scaffolding.
3. Before large installs, check free space, Python version and Node version, and choose compatible versions that exist in this environment. Set native thread limits to 2. Avoid needless package managers or multiple virtual environments.
4. Never claim results you have not measured. All dashboard data must be API-backed; uncertainty/confidence must not be invented; simulation-derived claims must visibly say so. Use example data in local `Demo Mode` only.
5. On UI work, inspect the actual image files (whatever their filenames) and reproduce the polished 5-screen StockPilot visual system as faithfully as responsive HTML/CSS allows. Make every main nav item functional, with sensible redirects or a real relevant screen.
6. Prefer a fully working vertical slice over unnecessary architecture. Keep all API, DB, CLI, and UI contracts consistent. Tests are mandatory and the final acceptance gate is mandatory.
7. If you hit a problem, search the local repository, read error output and repair; do not ask me minor implementation questions. If full implementation won't fit in one context, save current tested state and exact resume steps in PROGRESS.md; continue when context permits.

**Deliverables in workspace root:** `frontend/`, `backend/`, local run scripts, tests, `.gitignore`, `README.md`, model/data architecture docs, and `cursor-prompts/PROGRESS.md`. No AWS provisioning during this task. Finish with exact Windows and Unix startup commands and an evidence-based test summary. Start working now.
