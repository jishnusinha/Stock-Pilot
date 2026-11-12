# Phase 19 — Optional M5 real-data importer and truthful portfolio polish

## Strict priority
**Optional enhancement**. The app must already work end to end with generated demo data. Do not make local startup depend on Kaggle auth/network. If storage/time is limited, implement import parser lightly and skip downloading datasets, documenting as optional.

## M5 importer (only if manageable)
User may separately download M5 Forecasting Accuracy competition files. Create `python -m app.cli import-m5 --path <existing-local-dataset-dir> --store <store-id> --skus 200 --days 365` with helpful validation and dry-run. Do not download Kaggle automatically. File names typically `sales_train_validation.csv` or `sales_train_evaluation.csv`, `calendar.csv`, `sell_prices.csv`; support clear errors for missing files.

## Ingestion memory constraints
- Wide M5 sales file can be large in RAM even if disk file size seems small. Read appropriate columns / limited rows when possible, avoid copying full wide frames; use CSV streaming/chunking to extract **one store, 200 SKUs**.
- Build SKU mapping and known calendar/sale-price features correctly. No inventing missing inventory or supplier facts from M5; supplement inventory simulation with explicit provenance.
- Create **separate** data profile or DB path for M5 import. Default seed stays reproducible.
- Metrics trained on sales from M5 may be labeled `M5_HISTORICAL`; risk/ETA/waste remain `SIMULATED_SUPPLY` unless actual labeled sources exist. Never claim retailer-specific real-world cost savings based only on M5.

## Portfolio enhancements
- `docs/interview-demo.md`: 3–5-minute live demo script showing predictive SKU alert → scenario adjustment → order approval/receiving → agent trace → backtest comparison, with clearly marked demo assumptions.
- `docs/model-methods.md`: feature table, 10 estimators, inference DAG, weak points, noncausal price warning, calibration approach, provenance and limitations.
- `docs/tradeoffs.md`: why SQLite, one FastAPI process, no GPU, single-instance, future RDS/Postgres path, AWS resource/cost uncertainty.
- `docs/mockup-map.md`: final screenshot references and implemented routes.
- GitHub-ready README with architecture diagram in Markdown / Mermaid and a feature gif if naturally available; don't install heavy tools just for this.

## Acceptance
M5 missing? Clear optional documentation only; synthetic setup still passes. If implemented, importer test with miniature **locally constructed M5-shaped fixtures**, not Kaggle network access. No leakage from M5 future pricing or calendar labels into features.
