# Model methods & limitations

## Features (valid time)
Product/category codes, DOW/month sin-cos, promo/event, price, lags 1/7/14/28, rolling mean/std **shifted by 1**, zero-sale ratio, relative price. No future sales in features.

## Splits
Warmup 28d → train → val 28d → holdout 28d. Chronological only.

## Weak points
- Synthetic demand ≠ real shopper behavior.
- Price coefficients are **associations on generated data**, not causal elasticities.
- Stockout/excess probabilities come from **inventory simulators**, not warehouse outcomes.
- IsolationForest anomaly scores are not calibrated probabilities.
- p10–p90 is nominal **80%** coverage, not 95%.

## Calibration
Binary risk models may report Brier/precision when both classes exist; otherwise `N/A`. Do not map regression bands to “94.7% confidence.”
