# Optional real data (M5) — not required

StockPilot runs fully on the local **SYNTHETIC_DEMO** generator. Connecting the M5 forecasting competition dataset is optional future work and **must never** be a setup dependency.

## If you add M5 later
1. Download M5 yourself (Kaggle account is your responsibility).
2. Place CSVs under a gitignored path such as `backend/data/external/m5/`.
3. Write an importer that maps to `products` + `sales` with `training_source=M5` provenance.
4. Retrain agents and re-evaluate; keep synthetic demo as the default `bootstrap` path.
5. Label UI provenance clearly when M5 is active.

Do **not** commit M5 files or Kaggle credentials. Do not call Kaggle APIs from bootstrap.
