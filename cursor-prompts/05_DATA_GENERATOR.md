# Phase 05 — Deterministic, internally consistent synthetic retail dataset

## Why
No account, credential, Kaggle download, or network request should be necessary for first run. All generated business data must be explicitly labeled `SYNTHETIC_DEMO` across UI/docs/metadata. Never claim simulated demand reflects real retail customers.

## Required CLI
From backend: `python -m app.cli seed --products 200 --days 365 --seed 42` and `python -m app.cli reset-demo --confirm` (destructive command is explicit and refuses to execute without `--confirm`). Provide a generic `python -m app.cli bootstrap` later. Implement `--help`.

## Dataset design
- Fixed `demo_as_of` date = `2026-11-01` by default; generate dates `as_of - (days-1)` through `as_of`. Show `Demo snapshot as of ...` instead of misleading current calendar claims.
- Generate exactly 200 realistic, stable SKU identifiers, product labels, six categories, 8–12 suppliers, cost/price in paise, pack sizes, limited shelf lives for some products, initial stock and reorder points.
- Per product/day: generated units sold with weekly/seasonal effects, price variation, occasional promotions, sparse/intermittent categories, trend and stochastic noise. Use independent random substreams (numpy Generator seed) for repeatability.
- Price can change over time in the simulator so price response can be learned on *synthetic* labels; ensure quantity is nonnegative integer; promo and event flags are explicitly generated. Don't imply causal findings from observational data.
- Generate separate simulated supplier delivery samples and inventory trajectory/scenario samples **for model training**, with source tag `SIMULATED_SUPPLY`; this is where lead-time, stockout and excess labels originate. Store moderately sized simulator data as a compressed lightweight file or create it deterministically during training; avoid loading many full copies.
- Historical stock on hand is the demo snapshot, not a derivation from historical `sales` unless inventory movement history is separately modeled. Make this limitation clear in docs.

## Hygiene
- Avoid historical data leakage: no features that read future sales into row t; promo may be known ex ante, price at t may be input, inventory snapshot only used at scenario time.
- Use vectorized generation, insert with `executemany` in chunks, never one ORM object for each row.
- Run this on 200×365 = 73,000 sales rows; implement optional 50×180 quick dev run and 200×540 extended run.
- A few SKUs must intentionally be low-stock, some overstock, some intermittent, for functional demo coverage. These are *seeded scenarios*, not copied screenshot metrics.

## Tests
- Same seed and args produce same row counts and stable checksum of canonical data samples.
- Different seed changes some demand observations.
- Exactly N products and N×days unique daily sales rows (unless documented explicit missingness).
- No negative stock, negative prices, or nonsensical quantities.
- No internet calls. Document generation duration and resulting DB size.
