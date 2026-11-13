# Real-data evaluation — UCI Online Retail (`REAL_RETAIL_UCI`)

## Why UCI Online Retail

StockPilot’s demo track is synthetic. Interviewers also expect evidence that forecasting code works on **external, attributed transaction data**. UCI Online Retail (dataset 352) is public, CC BY 4.0, and widely cited.

It is **not** a full inventory system ground truth.

## What the dataset contains

- ~541,909 invoice lines (01 Dec 2010 – 09 Dec 2011)
- Stock codes, quantities, GBP unit prices, invoice timestamps, optional customer IDs
- Cancellations / returns mixed with sales

## What it does **not** contain

- On-hand inventory balances
- Supplier lead times or promised ETAs
- Verified stockouts / lost sales
- Store opening calendars

**Observed sales ≠ unconstrained demand.**

## Cleaning summary (this workspace run)

| Metric | Value |
|--------|------:|
| Source rows | 541,909 |
| Distinct StockCodes (raw) | 4,070 |
| Positive sales rows kept | 527,899 |
| Excluded / returns audit rows | 14,010 |
| Raw SHA-256 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |

Policies: cancellations audited separately; returns not subtracted from unrelated dates; admin codes (POST, DOT, …) excluded; exact duplicate lines retained; large orders retained unless failing other rules. Currency remains **GBP**.

## Feature engineering

Leakage-safe lags (1/7/14/28), shifted rolling mean/std, calendar encodings, historical zero-sale share, historical price features. Rolling stats use `shift(1)`.

## Temporal split (100 SKUs, seed 42)

| Split | Dates | Rows |
|-------|-------|-----:|
| Train | 2010-12-01 → 2011-10-14 | 31,800 |
| Validation | 2011-10-15 → 2011-11-11 | 2,800 |
| Test | 2011-11-12 → 2011-12-09 | 2,800 |

SKU selection used **training-window activity only**. December 2011 is incomplete in the source.

## Models trained (isolated artifacts)

Path: `experiments/real_data/uci_online_retail/models/`

- Demand: `HistGradientBoostingRegressor`
- Interval: quantile `GradientBoostingRegressor` p10/p90
- Intermittence: logistic regression for **zero recorded-sales day** (not verified stockout)

Synthetic demo models under `backend/artifacts/models/` are untouched.

## Evaluation protocol

**Rolling one-step-ahead** on the test calendar. Prior test actuals may enter later lags. This is **not** a fixed-origin 28-day multi-horizon forecast.

## Holdout results (measured)

| Method | WAPE | MAE | RMSE |
|--------|-----:|----:|-----:|
| HistGradientBoosting | **0.6611** | 25.91 | 89.46 |
| Moving average 28 | 0.8869 | 34.76 | 90.85 |
| Seasonal naive (lag-7) | 0.9558 | 37.46 | 108.10 |

- Empirical p10–p90 coverage: **0.831** (nominal ~80% band; **not** a 95% CI)
- Best WAPE method: `hist_gradient_boosting`
- Intermittence Brier (zero recorded-sales day): 0.159

Artifacts: `experiments/real_data/uci_online_retail/reports/` (`metrics.json`, `baseline_comparison.csv`, `test_predictions.csv`, …).

## Interpretation & limitations

- ML beat both baselines on this SKU set and protocol; that does **not** generalize to all retail settings.
- Dense zero-filling reconstructs absence of recorded sales only.
- Does **not** validate StockPilot’s supplier ETA, stockout, excess, or reorder optimizer agents.

## Commands

See [data/README.md](../data/README.md) and [real-data-interview-guide.md](real-data-interview-guide.md).
