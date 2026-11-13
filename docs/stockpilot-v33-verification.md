# StockPilot 3.3 — Verification report

**Date:** 2026-11-13  
**Base commit before work:** `7889eb882b551b752fd3957aa6e8607ce77d121a`  
**Experiment id:** `REAL_RETAIL_UCI`

## Source acquisition

| Item | Value |
|------|-------|
| Status | **Downloaded** from official UCI ZIP |
| URL | https://archive.ics.uci.edu/static/public/352/online+retail.zip |
| Page | https://archive.ics.uci.edu/dataset/352/online+retail |
| DOI | https://doi.org/10.24432/C5BW33 |
| License | CC BY 4.0 |
| Local path | `data/real/uci_online_retail/raw/Online Retail.xlsx` |
| Bytes | 23,715,344 |
| SHA-256 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |

## Processing

| Metric | Value |
|--------|------:|
| Source rows | 541,909 |
| Positive sales rows | 527,899 |
| Daily sales rows (all SKUs, observed days) | 275,427 |
| Selected SKUs | 100 (train-only activity, seed 42) |
| Train rows | 31,800 |
| Validation rows | 2,800 |
| Test rows | 2,800 |
| Train dates | 2010-12-01 → 2011-10-14 |
| Val dates | 2011-10-15 → 2011-11-11 |
| Test dates | 2011-11-12 → 2011-12-09 |

## Holdout metrics (rolling one-step-ahead)

| Method | WAPE | MAE | RMSE |
|--------|-----:|----:|-----:|
| HistGradientBoosting | 0.6611 | 25.91 | 89.46 |
| Moving average 28 | 0.8869 | 34.76 | 90.85 |
| Seasonal naive (lag-7) | 0.9558 | 37.46 | 108.10 |

- Best WAPE method: `hist_gradient_boosting`
- Empirical p10–p90 coverage: 0.8307
- Mean interval width: 52.89
- Intermittence Brier (zero recorded-sales day): 0.1590
- Model version: `real_uci_v1`

## Artifact paths (isolated from synthetic demo)

- Models: `experiments/real_data/uci_online_retail/models/`
- Reports: `experiments/real_data/uci_online_retail/reports/`
- Splits: `data/real/uci_online_retail/splits/`
- Samples: `data/real/uci_online_retail/samples/`
- Synthetic models unchanged: `backend/artifacts/models/`
- Demo DB unchanged: `backend/data/stockpilot.db`

## CSV sizes (approx.)

| File | MB |
|------|---:|
| Online Retail.xlsx | 22.6 |
| transactions_clean.csv | 66.1 (gitignored) |
| daily_sales.csv | 24.8 (gitignored) |
| train.csv | 3.1 |
| validation.csv | 0.3 |
| test.csv | 0.3 |
| test_predictions.csv | present under reports/ |

## Automated checks

| Check | Result |
|-------|--------|
| Backend pytest (baseline) | 67 passed |
| Backend pytest (final) | **81 passed** |
| Frontend vitest | **25 passed** (after Real Performance tests) |
| Frontend production build | **pass** |
| Synthetic demo isolation | Real models not under `backend/artifacts/models` |

## API

Read-only routes under `/api/real-data/*` (status, summary, metrics, baselines, predictions, products, metadata, CSV exports). GET handlers do not train.

## UI

Model Performance → evaluation source selector:

- Synthetic Demo (unchanged charts / policy replay)
- Real Retail Evaluation (KPIs, actual vs predicted, baselines, uncertainty, dataset panel)

## Limitations (honest)

- Observed sales ≠ unconstrained demand
- No supplier / stockout / excess ground truth → those agents remain synthetic-only
- Rolling one-step-ahead ≠ fixed-origin 28-day path forecast
- p10–p90 ≠ 95% confidence interval
- Unit prices are GBP, never INR
- December 2011 source coverage is incomplete
- D: drive free space was tight (~1 GB); large processed CSVs are gitignored

## Remaining optional work

- Commit when authorized (not done automatically)
- Re-run `real-data-prepare` after cancellation-reason priority fix to refresh reason counts in `returns_summary.csv` / quality JSON (sales membership unchanged)
- Optional multi-horizon fixed-origin evaluation if needed later
