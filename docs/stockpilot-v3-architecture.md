# StockPilot 3.0 architecture

StockPilot 3.0 adds a descriptive inventory layer beside the existing 10-agent forecast path and the deterministic reorder optimizer. The three layers share product identity: an analytics ranking opens the product drawer, the drawer opens the simulator with `?product=`, and a recommendation with a real `trace_id` opens Agent Intelligence.

```
sales + products + suppliers
        │
        ▼
build-analytics (seed 42)  →  analytics_runs
        │                      inventory_ledger
        │                      inventory_daily_snapshots
        │                      inventory_receipts
        ▼
inventory_analytics.py  →  /api/analytics/*
        │
        ▼
/analytics  (URL filters, charts, ABC–XYZ, slow stock, suppliers)

products.stock_on_hand  →  live KPIs on Command Center and overview
forecasts + risk cache  →  excess proxy, slow-moving cover, product drawer
reorders                →  calendar; receive updates live stock only
```

## Schema

Migration `v3` is additive. `migrate()` still records `v1` and `v3`. Tables:

| Table | Role |
|---|---|
| `analytics_runs` | Generation id, source, seed, snapshot date, version `v1`, status, notes |
| `inventory_ledger` | Opening, receipt, sale, return, adjustment, write-off events |
| `inventory_daily_snapshots` | One row per product, date, and run |
| `inventory_receipts` | Replenishment and reconciliation receipts, with delay and supplier |

Uniqueness is `(dataset_source, seed, snapshot_date, version)` on runs and `(run_id, product_id, snapshot_date)` on snapshots. Child rows cascade when a run is rebuilt with `--force`. Indexes cover run/date and product/date lookups.

`seed.py` deletes these four tables before products when they exist, so a later destructive reseed does not fail on foreign keys. Normal operation does not reseed.

## Generation

`python -m app.cli build-analytics --seed 42`

`inventory_history.py` walks each product with `numpy` Generator seeded by `seed + product_id * 1_000_003`. It does not change `sales`, `products.stock_on_hand`, forecasts, or model rows.

- Opening stock starts from reorder point and mean demand times lead time plus 14 days.
- Replenishment orders are pack-rounded when stock plus inbound falls below the reorder point. Delay is 0 when the draw is below `delivery_reliability`, otherwise 1–3 days. Arrivals inside the calendar become `kind='replenishment'` receipts.
- Fulfilled sales cannot exceed stock. Remaining demand is unmet.
- Small deterministic adjustments, rare write-offs, and next-day returns (about 4 percent of a day's fulfilled units when that day sold at least 8 and the draw is below 0.05) are labeled `SYNTHETIC_RECONSTRUCTED`.
- On the snapshot date the closing balance is forced to `products.stock_on_hand` with a reconciliation receipt (`RECONCILE_TO_SNAPSHOT`) or an extra write-off.

A complete run for the same source, seed, snapshot date, and version is reused. `--force` rebuilds it. The run notes store the checksum and the up/down/matched reconciliation counts.

## API and UI

`analytics_routes.py` is mounted on the existing `/api` router. Responses use `AnalyticsResponse` (`extra=allow`) so each endpoint can return its own payload without a second schema per chart. Filter parsing returns 400 for bad dates and 404 for an unknown product or supplier.

The page is `frontend/src/pages/InventoryAnalytics.tsx`, lazy-loaded at `/analytics`. Filter state lives in the URL (`from`, `to`, `year`, `month`, `category`, `supplier`, `product`, `rank`, `cell`). Chart fetches omit `rank` and `cell`. Month chips, category bars, the ranking toggle, and ABC cells update that state. Product clicks open `ProductDetailDrawer`.

Theme preference is `localStorage` key `stockpilot-theme`. Dark mode sets `data-theme="dark"` on `documentElement` before first paint. Light mode removes the attribute so `:root` stays the light palette.

## Provenance

| Label | Meaning |
|---|---|
| `SYNTHETIC_DEMO` | Existing catalog, sales, and models |
| `SYNTHETIC_RECONSTRUCTED` | Generated ledger, snapshots, and receipts |
| `SIMULATED_SUPPLY` | Existing risk labels and what-if paths |
| `SIMULATED_POLICY_REPLAY` | Small-sample policy comparison on the performance page |

Supplier on-time rates from reconstructed receipts are simulated. Catalog `delivery_reliability` is a generation parameter, not a measured rate.

## What stays unchanged

The 10 scikit-learn agents, their artifact versions, the orchestrator, and the reorder lifecycle (pending → approved → received, or pending → rejected) are unchanged. Approval does not increase stock. Receiving increases stock once. Historical snapshots stay immutable after that receipt.
