# Architecture

```
Browser (React + Vite)
   │  HTTP JSON  /api/*
   ▼
FastAPI (Uvicorn) ── CORS localhost:5173
   │
   ├─ Services: dashboard, simulate, orchestrator, optimizer, performance
   ├─ Agents (10 sklearn estimators, lazy-loaded joblib)
   └─ SQLite  backend/data/stockpilot.db
         + artifacts/models/*.joblib
```

Local-only. No Redis, Postgres, Docker, AWS, or LLM.

## Decision DAG
1. Features / known state  
2. `calendar_effect`, `price_response`, `intermittence`, `sales_anomaly`, `product_similarity`  
3. `demand` → `demand_interval`  
4. `supplier_eta`  
5. `stockout_risk`, `excess_risk`  
6. Deterministic **reorder optimizer** (not a trained agent)

## Provenance
- Sales/catalog: `SYNTHETIC_DEMO`  
- Lead-time / stockout / excess labels: `SIMULATED_SUPPLY`  
- Business savings on Performance page: simulation-derived
