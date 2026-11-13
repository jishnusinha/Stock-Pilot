# Interview walkthrough — Real retail evaluation (≈8–10 minutes)

Use this sequence on a laptop with the API + UI running and `real-data-evaluate` already completed.

## 1. Dataset introduction

Open Model Performance → **Real Retail Evaluation**.  
State: official UCI Online Retail, CC BY 4.0, GBP, experiment id `REAL_RETAIL_UCI`, isolated from `SYNTHETIC_DEMO`.

## 2. Raw CSV walkthrough

Open `data/real/uci_online_retail/samples/raw_sample.csv` (or download via `/api/real-data/samples/raw.csv`).

Explain: `InvoiceNo`, `StockCode` (string), `Quantity`, `InvoiceDate`, `UnitPrice` (GBP).

## 3. Data-quality challenges

Point to `experiments/real_data/uci_online_retail/reports/data_quality.json`:

- Cancellations (`C…` invoices) and negatives
- Missing CustomerID / Description
- Admin codes (POST, fees)
- Returns not uniquely matchable to sales

## 4. Preprocessing pipeline

Code: `backend/app/real_data/preprocess.py`  
Outputs: `transactions_clean.csv`, `returns_summary.csv`, `daily_sales.csv`.

## 5. Feature engineering

Code: `backend/app/real_data/features.py`  
Lags + shifted rolling stats; no future targets; price never taken from the future.

## 6. Chronological splits

Open `data/real/uci_online_retail/splits/{train,validation,test}.csv`.  
Emphasize: **no shuffled `train_test_split`**. Train ends before validation before test.

## 7. Model training

Artifacts: `experiments/real_data/uci_online_retail/models/`  
Version `real_uci_v1`. Separate from synthetic `backend/artifacts/models/`.

## 8. Actual vs predicted demo

UI chart for a selected StockCode; values come from `test_predictions.csv`.  
Label: rolling one-step-ahead.

## 9. Baseline comparison

Show WAPE bars: HGB vs seasonal naive vs moving average.  
Report whichever method won honestly (this run: HGB).

## 10. Limitations and next experiments

UCI cannot validate supplier ETA / stockout / excess / reorders.  
Switch UI back to **Synthetic Demo** and show the ten-agent operational stack.

### Reproduce

```powershell
cd backend
python -m app.cli real-data-all --max-products 100 --seed 42 --threads 2
```
