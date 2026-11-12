# Ten ML agents (non-LLM)

| Agent | Estimator | Training source | Role |
|---|---|---|---|
| demand | HistGradientBoostingRegressor | SYNTHETIC_DEMO sales | Next-day / multi-day demand mean |
| demand_interval | Quantile GradientBoosting (p10/p90) | SYNTHETIC_DEMO | Uncertainty band (nominal 80%) |
| intermittence | LogisticRegression / HGB classifier | SYNTHETIC_DEMO | P(zero sale) |
| price_response | Ridge / ElasticNet | SYNTHETIC_DEMO price variation | Simulated price–demand association |
| calendar_effect | Ridge | SYNTHETIC_DEMO | DOW/month/promo effects |
| sales_anomaly | IsolationForest | SYNTHETIC_DEMO residuals | Anomaly score (not a probability) |
| product_similarity | NearestNeighbors | SYNTHETIC_DEMO embeddings | Similar SKUs |
| supplier_eta | RandomForestRegressor ≤60 trees | SIMULATED_SUPPLY deliveries | Expected lead days |
| stockout_risk | HistGradientBoostingClassifier | SIMULATED_SUPPLY inventory paths | P(stockout) |
| excess_risk | Logistic / boosted classifier | SIMULATED_SUPPLY trajectories | P(excess/spoilage) |

CLI:
```
python -m app.cli train --all --threads 2
python -m app.cli model-status
python -m app.cli evaluate
```

Artifacts: `backend/artifacts/models/<agent>/<version>.joblib` + `.meta.json`.
