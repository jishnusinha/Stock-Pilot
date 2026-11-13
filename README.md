# StockPilot

Local-first **inventory intelligence** demo for one synthetic retailer, plus an isolated **real-retail ML evaluation** track (StockPilot 3.3).  
**No LLM.** Ten compact scikit-learn agents + a deterministic reorder optimizer, reconstructed inventory-history analytics (3.0), predictive Inventory Analytics (3.2), and UCI Online Retail holdout benchmarking (3.3).

```
React (Vite)  →  FastAPI  →  SQLite + joblib models
             ↘  data/real + experiments/real_data (isolated)
```

Money in the demo is integer **paise** (shown as ₹). Demo provenance: `SYNTHETIC_DEMO` / risk labels `SIMULATED_SUPPLY`. Real evaluation uses **GBP** UCI transactions (`REAL_RETAIL_UCI`) and never overwrites demo DB/models.

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

## Docker (EC2 / single host)

One container serves the built UI (nginx on port 80) and proxies `/api` to FastAPI. SQLite + models live on a named volume under `/data`.

**Recommended for AWS free tier:** train on your PC, pack the DB/models into the image, then the micro only *serves* — it does not train.

### Train locally → bake seed → push → run on EC2

```powershell
cd "c:\D Drive\ML Master projects\StockPilot"

# 1) Train on your machine (use --fast on modest PCs)
.\scripts\bootstrap.ps1 --fast
# optional analytics history (same as local UI):
cd backend; .\.venv\Scripts\python -m app.cli build-analytics --seed 42; cd ..

# 2) Copy DB + models (+ evaluation JSON) into deploy\seed
.\scripts\export-docker-seed.ps1

# 3) Build image (includes /seed) and push
docker compose build
docker tag stockpilot:latest <your-dockerhub-user>/stockpilot:latest
docker login
docker push <your-dockerhub-user>/stockpilot:latest
```

**On Ubuntu EC2** (security group: TCP 22 from your IP, TCP 80 from anywhere). Swap is optional if you shipped a seed (no training):

```bash
sudo apt-get update && sudo apt-get install -y docker.io
sudo usermod -aG docker "$USER"   # then log out/in

docker pull <your-dockerhub-user>/stockpilot:latest
docker run -d --name stockpilot --restart unless-stopped \
  -p 80:80 \
  -v stockpilot-data:/data \
  <your-dockerhub-user>/stockpilot:latest

docker logs -f stockpilot
# look for: "Loading pre-trained seed from /seed"
```

UI: `http://<ec2-public-ip>/` · API docs: `/docs`.

Entrypoint order: if `/data/stockpilot.db` exists → reuse volume; else if `/seed/stockpilot.db` exists → copy seed into `/data`; else → bootstrap in-container (slow / may OOM on 1 GB).

Reseed volume: `docker rm -f stockpilot && docker volume rm stockpilot-data` then `docker run` again.

### Build without a seed (not ideal on free tier)

```bash
docker compose up -d --build
```

Defaults then train **50×90 / 1 thread** inside the container. Prefer ≥2 GB swap on t2/t3.micro if you go this route. Full **200×365** needs roughly ≥8 GB RAM.

## Manual commands (equivalent)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --no-cache-dir -r requirements.txt
$env:OMP_NUM_THREADS=2
python -m app.cli bootstrap --products 200 --days 365 --seed 42 --threads 2 --fast
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# additive analytics history (does not rewrite sales, stock, or models)
python -m app.cli build-analytics --seed 42

# other terminal
cd frontend
npm install
npm run dev
```

## Routes

| Path | Screen |
|---|---|
| `/` | Command Center |
| `/analytics` | Inventory Analytics (Overview · Predictive Intelligence · Decision Insights · Data Quality) |
| `/inventory` | Inventory Explorer |
| `/simulator` | What-If Simulator |
| `/agents` | Agent Intelligence |
| `/performance` | Model Performance |
| `/reorders` | Reorder workflow |

Sidebar items like Products / Forecast / Reports redirect to the relevant live page. The mockup “Upgrade” card is replaced by a **Demo Mode / ML status** panel.

## Ten agents

See [docs/ml-agents.md](docs/ml-agents.md). Orchestration DAG: calendar/price/intermittence/anomaly/similarity → demand (+interval) → supplier ETA → stockout/excess risk → **optimizer**.

## Predictive analytics (3.2)

Inventory Analytics connects descriptive history to persisted ML outputs (no retrain on page load):

- Demand outlook + 7/14/28-day horizons from `forecasts` (Demand Interval Agent)
- Inventory value projection (no-reorder vs recommended) via stock-flow simulation
- Stockout / excess panels (probabilities never summed; excess **proxy** ≠ Excess Risk Agent)
- Optimizer recommendations + deterministic explanations + simulator/agent-trace links

Docs: [docs/stockpilot-v32-predictive-analytics.md](docs/stockpilot-v32-predictive-analytics.md) · [docs/ml-analytics-integration-design.md](docs/ml-analytics-integration-design.md) · [docs/stockpilot-v32-verification.md](docs/stockpilot-v32-verification.md)

```powershell
# example predictive calls
Invoke-RestMethod "http://127.0.0.1:8000/api/analytics/predictive/overview?horizon_days=28"
Invoke-RestMethod "http://127.0.0.1:8000/api/analytics/predictive/inventory-projection?mode=recommended&horizon_days=14"
```

## Real retail evaluation (3.3)

Official UCI Online Retail → clean CSVs → chronological splits → leakage-safe features → train HGB + quantiles + intermittence → baselines → holdout metrics.  
UI: **Model Performance → Real Retail Evaluation**. Does **not** validate supplier/stockout agents.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # includes openpyxl
python -m app.cli real-data-all --max-products 100 --seed 42 --threads 2
python -m app.cli real-data-status
```

Docs: [data/README.md](data/README.md) · [docs/real-data-evaluation.md](docs/real-data-evaluation.md) · [docs/real-data-interview-guide.md](docs/real-data-interview-guide.md) · [docs/stockpilot-v33-verification.md](docs/stockpilot-v33-verification.md)

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q

cd ..\frontend
npm test
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
- [UI v2 audit](docs/ui-v2-audit.md) · [UI v2 verification](docs/ui-v2-verification.md)  
- [Interview demo](docs/interview-demo.md) · [Optional M5](docs/optional-m5.md)  
- [StockPilot 3.0 architecture](docs/stockpilot-v3-architecture.md) · [Inventory metrics](docs/inventory-metrics.md) · [3.0 verification](docs/stockpilot-v3-verification.md)  
- Real data: [data/README.md](data/README.md) · [evaluation](docs/real-data-evaluation.md) · [interview guide](docs/real-data-interview-guide.md) · [3.3 verification](docs/stockpilot-v33-verification.md)  
- Progress: [cursor-prompts/PROGRESS.md](cursor-prompts/PROGRESS.md) · [3.2](cursor-prompts/STOCKPILOT_V32_PROGRESS.md) · [3.3](cursor-prompts/STOCKPILOT_V33_PROGRESS.md)

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

Dashboard / performance figures from inventory replay are marked **SIMULATED**. Purchase cash is never labeled as “savings.” The Command Center shows purchasing-cost inventory value and an excess-stock proxy. Historical inventory charts come from `python -m app.cli build-analytics` and are labeled **SYNTHETIC_RECONSTRUCTED**. They are not inferred by multiplying today’s stock by old prices, and a later goods receipt does not rewrite those snapshots. Price response is an **observational** association, not causal elasticity. Unmeasured latency/confidence shows **Not measured** / **N/A**.

Holdout demand evaluation uses **rolling one-step** chronological scoring (honest WAPE ≈ 0.29 on the demo seed) — not a single prediction compared to holdout means.
# .\scripts\start-api.ps1 