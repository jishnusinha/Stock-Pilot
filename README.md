# StockPilot

Local-first **inventory intelligence** demo for one synthetic retailer.  
**No LLM.** Ten compact scikit-learn agents + a deterministic reorder optimizer. UI matches the five screens in `mockup-ui/`.

```
React (Vite)  →  FastAPI  →  SQLite + joblib models
```

Money is stored as integer **paise** and shown as ₹. Dataset provenance: `SYNTHETIC_DEMO` / risk labels `SIMULATED_SUPPLY`.

## Prerequisites (verified on this workspace)

| Tool | Version tested |
|---|---|
| OS | Windows 10/11 (PowerShell) |
| Python | 3.12.9 |
| Node | 24.x / npm 11.x |
| RAM / disk | Aim ≥8 GB RAM; keep several GB free for `node_modules` + `.venv` |

No GPU, Docker, Redis, AWS, or API keys required after package install.

## Quick start — Windows PowerShell

```powershell
cd "c:\D Drive\ML Master projects\StockPilot"

# One-time deps
.\scripts\setup.ps1

# Seed 200 SKUs × 365 days, train 10 agents, evaluate (CPU threads=2)
.\scripts\bootstrap.ps1
# Optional faster estimators: .\scripts\bootstrap.ps1 --fast
# Destructive rebuild: .\scripts\bootstrap.ps1 --force --fast

# Terminal 1 — API
.\scripts\start-api.ps1

# Terminal 2 — UI
.\scripts\start-ui.ps1
```

- UI: http://127.0.0.1:5173  
- API docs: http://127.0.0.1:8000/docs  
- Demo snapshot date: **2026-11-01**

## Quick start — Linux / macOS

```bash
cd /path/to/StockPilot
chmod +x scripts/*.sh
./scripts/setup.sh
./scripts/bootstrap.sh          # add --fast if needed
./scripts/start-api.sh          # terminal 1
./scripts/start-ui.sh           # terminal 2
```

> Unix scripts were authored for portability; **this workspace verified Windows**.

## Manual commands (equivalent)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --no-cache-dir -r requirements.txt
$env:OMP_NUM_THREADS=2
python -m app.cli bootstrap --products 200 --days 365 --seed 42 --threads 2 --fast
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# other terminal
cd frontend
npm install
npm run dev
```

## Routes

| Path | Screen |
|---|---|
| `/` | Command Center |
| `/inventory` | Inventory Explorer |
| `/simulator` | What-If Simulator |
| `/agents` | Agent Intelligence |
| `/performance` | Model Performance |
| `/reorders` | Reorder workflow |

Sidebar items like Products / Forecast / Reports redirect to the relevant live page. The mockup “Upgrade” card is replaced by a **Demo Mode / ML status** panel.

## Ten agents

See [docs/ml-agents.md](docs/ml-agents.md). Orchestration DAG: calendar/price/intermittence/anomaly/similarity → demand (+interval) → supplier ETA → stockout/excess risk → **optimizer**.

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q

cd ..\frontend
npm run build

# or
.\scripts\verify.ps1
```

## Reset demo

```powershell
cd backend
.\.venv\Scripts\python -m app.cli reset-demo --confirm
.\.venv\Scripts\python -m app.cli bootstrap --products 200 --days 365 --seed 42 --threads 2 --fast
```

## Docs

- [Product contract](docs/product-contract.md) · [Mockup map](docs/mockup-map.md)  
- [Architecture](docs/architecture.md) · [API contract](docs/api-contract.md)  
- [Model methods](docs/model-methods.md) · [Agent dependency contract](docs/agent-dependency-contract.md)  
- [Tradeoffs](docs/tradeoffs.md) · [Local verification](docs/local-verification.md)  
- [Interview demo](docs/interview-demo.md) · [Optional M5](docs/optional-m5.md)  
- Progress: [cursor-prompts/PROGRESS.md](cursor-prompts/PROGRESS.md) · Repair: [cursor-prompts/REPAIR_PROGRESS.md](cursor-prompts/REPAIR_PROGRESS.md)

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` | Activate `backend/.venv` and reinstall requirements |
| PowerShell script blocked | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Port 8000/5173 in use | Stop other processes or change ports |
| Low disk | `pip install --no-cache-dir`; delete unused caches |
| DB locked | Stop the API process; delete `*-wal`/`*-shm` only if idle |
| Models missing | `python -m app.cli train --all --threads 2 --fast` |

## Honesty labels

Dashboard / performance figures from inventory replay are marked **SIMULATED**. Purchase cash is never labeled as “savings.” Price response is an **observational** association, not causal elasticity. Unmeasured latency/confidence shows **Not measured** / **N/A**.

Holdout demand evaluation uses **rolling one-step** chronological scoring (honest WAPE ≈ 0.29 on the demo seed) — not a single prediction compared to holdout means.
