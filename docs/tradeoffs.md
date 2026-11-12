# Design tradeoffs

| Choice | Why | Future |
|---|---|---|
| SQLite | Zero ops, laptop-friendly, transactional enough for demo | Postgres/RDS if multi-user |
| One FastAPI process | Simple; sequential ML fits avoid RAM thrash | Workers only if measured need |
| sklearn only | Fits 8 GB CPU laptops; no GPU/LLM cost | Keep LLM out of inventory math |
| Synthetic seed | No Kaggle/AWS dependency | Optional M5 importer |
| Precompute forecasts at bootstrap | Dashboard stays fast | Refresh job / CLI |

Public AWS exposure would require auth, HTTPS, rate limits, secrets, and tenancy — **not** provided in this local demo.
