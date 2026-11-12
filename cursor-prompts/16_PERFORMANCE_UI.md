# Phase 16 — Model Performance dashboard (screenshot 5)

## Layout
Replicate screenshot visual layout: 4 KPI cards top, baseline/model comparison chart, actual-vs-predicted time chart, calibration/coverage card, model versions table, and bottom business outcome simulation matrix.

## Required truthfulness
- Forecast WAPE = measured WAPE on chronological holdout; provide MAE tooltip, split dates and source tag.
- Stockout precision measured on holdout **simulated** scenarios, not represented as real operational accuracy.
- Savings only from documented backtested **simulated** costs; label `Illustrative simulation savings`. If missing, `N/A`.
- API p95 latency from actual load/smoke timing; show `Not measured` until data present.
- Model comparison must plot genuine historical comparisons: seasonal naive, rolling average, demand-only; don't compare things that use different target/horizons under one misleading metric. The full decision system should be compared on **decision metrics**, not on an invalid "multi-agent forecast WAPE" if forecast itself is unchanged.
- Quantile forecast p10–p90 interval nominal 80%; display empirical coverage and pinball loss (not fake predicted confidence calibration curve). For stockout probabilistic calibration, show a real reliability chart if enough samples, otherwise "Insufficient holdout samples".
- Model version table from `model_versions` persisted metadata. Deployment statuses are `local trained` / `not trained`, not invented `shadow/deployed` release history.

## Functional behavior
- Model picker, split/date label, selection links to agent inspector, export metrics as JSON/CSV if simple; all controls functional. Tooltip/data source disclosures.
- CTA re-run backtest should call a bounded async background local job only if implemented; otherwise provide command to run CLI, do not show a dead button.
- UI should gracefully render empty metrics before evaluation with a clear `python -m app.cli evaluate` instruction.

## Acceptance
- At least one displayed metric recomputes independently from output and matches persisted measurement.
- Screenshot visuals are close while the semantics are accurate.
- Nonexistent business gains are never shown as measured business savings.
- Model versions and training source visible to interviewer.
