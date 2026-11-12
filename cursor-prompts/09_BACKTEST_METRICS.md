# Phase 09 — Credible chronological evaluation and business outcome simulation

## Deliverable
`app/ml/backtest.py`, `app/ml/baselines.py`, `app/services/performance.py`, `python -m app.cli evaluate`, evaluation JSON + DB metrics rows. The dashboard must read these numbers from the API; **no fabricated screenshot figures**.

## Data splitting
Preserve the holdout 28-day interval from phase 06. Train only before the relevant cutoff, never predict a holdout day with its actual future demand lag. For multi-step backtests, roll predictions forward or use known historical observations only when that evaluation protocol explicitly permits one-step-ahead. Label 1-day and 28-day forecasts distinctly.

## Compare
- `seasonal_naive_7`: sales from same weekday last week, clamped nonnegative.
- `moving_average_28`: shifted trailing mean.
- `demand_only`: trained demand model without dependent decision modeling.
- `full_decision_system`: forecast + risk agents + optimizer (compare under the same **simulated** inventory environment).

## Forecast metrics
Holdout WAPE/MAE/RMSE for applicable models; quantile pinball and coverage; intermittent demand Brier if probabilities; risk classifier precision/recall/Brier on held-out *simulated* scenarios. Corroborate with numbers computed from predictions, not chosen constants.

## Business outcome experiments
Replay SKU inventory over a fixed 28–90 day scenario horizon with initial stock and supplier events. Compare a fixed reorder rule, forecast-only reorder rule, and the full multi-agent optimizer using same sampled demand paths and supply randomness per strategy to reduce noise. Record lost-sales units, stockout days, average inventory, unsold stock, holding cost, purchase spend, fulfilled revenue and illustrative net profit/cost proxy. Make business assumptions explicit (holding penalty, lost sales penalty, no real demand labels for future paths). Do not add or display arbitrary percentages.

## Performance measurements
Log p50/p95 endpoint durations using real timing samples. If no meaningful distribution or enough requests exist, show `Not measured`. Present model versions and their actual data provenance. Any UI label "95% confidence" requires a genuinely defined 95% statistical/quantile interval; default trained p10–p90 is nominal **80%** coverage, not 95%.

## Acceptance
- `python -m app.cli evaluate` produces DB rows and evaluation JSON, and can be re-run idempotently.
- Recompute at least one displayed WAPE number from saved predictions in a test.
- Nonexistent metrics display `N/A`, never `0`, and clear simulated vs held-out real-world distinction.
- Test proving no holdout targets leaked into the training feature frame.
