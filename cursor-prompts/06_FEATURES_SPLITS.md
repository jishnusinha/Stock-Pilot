# Phase 06 — Training feature pipeline and temporal evaluation

## Create
`app/ml/features.py`, `app/ml/splits.py`, `app/ml/metrics.py`, `app/ml/artifacts.py`, tests. This is shared infrastructure; do not create ten incompatible dataframes.

## Contracts
Daily supervised rows keyed by `(product_id, date)` with target `units`. Features include (all computed at valid time): product/category encoding, day-of-week/month, sin/cos cyclicality, promo/event flags known for date, today's listed price, lags 1/7/14/28, past rolling mean/std over 7/28 days with **shift(1)**, historical zero-sales ratio, and price-relative-to-history. Persist/record feature names and transformation metadata. Never leak target into its own features; no random train/test split.

## Split
Use 365 historical days with final 28 days reserved untouched as holdout; preceding 28 days validation; earlier history training after the first 28 days needed for lags. If insufficient rows, fail clearly or use a smaller explicitly stated split for quick-dev mode. Use rolling-origin evaluation for a small group of folds when affordable. No future information used in feature construction.

## Metrics
- Regression: MAE, RMSE, and WAPE with carefully defined denominator (if denominator 0, return `not applicable` rather than divide by zero).
- Quantiles: pinball loss at q=.10/.90; empirical coverage of interval [p10,p90] (nominal 80%); interval width.
- Probabilities: precision/recall/F1 and Brier score; if a test fold has only one class, report `not available` rather than invent AUC.
- Calibration metrics only for true binary outcome probabilities; don't call regression uncertainty bands "94.7% model confidence".
- Performance: peak RAM if measurable, artifact size, prediction time and p95 API endpoint time from measured requests.

## Training efficiency
- Use `float32` for numeric ML features where feasible and compact category codes.
- Set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS` no higher than 2 **before** importing NumPy/sklearn where possible; model `n_jobs<=2`, no CPU oversubscription.
- One estimator at a time, release intermediate matrices and garbage collect; save compressed small joblib artifacts. Avoid repeated full DataFrame copies.
- Save a JSON metadata file for each agent (`name`, `version`, `seed`, `estimator`, `source`, `dataset_size`, `feature_columns`, `split dates`, `metrics`, `created_at`, `artifact_size`).

## Acceptance
Unit test with a deliberately crafted tiny dataset proves lag and rolling features are shifted; test dates in train/validation/holdout don't overlap. A demo training matrix uses <1 GB observed peak incremental process memory if measurable; document actual result instead of making unverified claim.
