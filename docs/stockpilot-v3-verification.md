# StockPilot 3.0 verification

Recorded 12 November 2026 on the local Windows workspace. Figures below are measured, not targets.

## Baseline before the analytics tables

- Backend: `pytest -q` — 40 passed.
- Frontend: `npm run build` succeeded.
- `PRAGMA integrity_check` — ok. 200 products, 73,000 sales rows, 10 `model_versions`.
- Database file about 8,224,768 bytes.
- All 10 agent artifacts present at version 1.0.0.
- `mockup-ui/` images were not in the workspace, so no pixel comparison to Power BI screenshots was possible. `docs/mockup-map.md` was present.

## Analytics generation

`python -m app.cli build-analytics --seed 42` on the existing database.

| Check | Result |
|---|---|
| Run | id 1, status complete, version v1, seed 42, snapshot 2026-11-01 |
| Checksum | `3744869:550672:73000:74448` |
| Second invocation | reused run 1 |
| Reconciliation | 158 SKUs receipt up, 42 write-off down, 0 already matched |
| Sales rows | still 73,000 |
| Model versions | still 10 |
| Integrity | ok |
| Database file | 28,811,264 bytes |

The forward simulation did not land on current stock for any SKU. The snapshot-day receipt or write-off is explicit in `analytics_runs.notes`. Sales rows were not edited.

Live overview after generation: inventory value 91,603,896 paise, turnover about 54.003, DIO about 6.759 days, excess proxy 11,515,560 paise. Live value matched period-end value before any later receipt. Turnover near 54 is the real aggregate for this fast grocery panel, not a formula error. The gauge reference target is 6 and the arc caps at 12.

## Automated tests after implementation

- `pytest -q` in `backend`: **45 passed** (16.26s) on 12 November 2026, after supplier receipt stats were scoped to the active product filter. Includes conservation, continuity, valuation, demand preserved, snapshot reconciliation, idempotence, identical checksums, unchanged sales and stock, model rows kept, turnover = COGS / average inventory, category filter, movement conservation, receive-once without snapshot rewrite, empty window, 400/404, ABC cells, slow-moving without expiry, supplier rate in [0, 1], and no `estimated_savings_paise`.
- `npm test` in `frontend`: **11 passed** (7 files) the same day. Covers ranking toggle, product drawer actions, month selection, theme storage, and analytics query keys.
- `npm run build` succeeded earlier in the session. The analytics route is a separate chunk (`InventoryAnalytics-*.js`, about 24 KB). The supplier-stat change after that build is backend-only.

## Browser

Dev servers already running: UI `http://127.0.0.1:5173`, API `http://127.0.0.1:8000`.

| Viewport | Overflow (`scrollWidth - clientWidth`) |
|---|---|
| 1440 × 900 | 0 |
| 1280 × 900 | 0 |
| 1024 × 900 | 0 |
| 768 × 900 | 0 |
| 390 × 844 | 0; the title fit inside the viewport |

The IDE browser panel crops screenshots, so layout evidence is the overflow measurement plus the accessibility tree, not a full-page capture.

Checked in the browser:

- `/analytics` loaded KPIs (inventory value ₹9,16,039, stock 22,720, turnover 54.00, inventory-to-sales 0.03, DIO 6.8, excess ₹1,15,156), month chips, value ranking, ABC matrix, and supplier cards labeled simulated.
- Category Dairy wrote `?category=Dairy`, replaced the top product with Dairy Item 193, reduced ABC counts, and scoped supplier product counts.
- `GET /api/analytics/suppliers?category=Dairy` returned Northwind Foods with 9 products and 320 simulated receipts, against 1,305 unfiltered receipts for the unfiltered leader. Receipt stats follow the product filter.
- Opening Dairy Item 193 showed the product drawer. What-if reorder navigated to `/simulator?product=193` and selected SKU-0193.
- Dark theme set `data-theme=dark` and the toggle read “Switch to light theme” on the simulator, Command Center, inventory, agents, reorders, and performance. Light theme was restored afterward.
- `/` showed Inventory value (₹9,16…) and did not show a savings KPI.
- `/inventory` rendered Inventory Explorer.
- `/agents` reported 10/10 models.
- `/reorders` rendered the replenishment timeline.
- `/performance` states pooled WAPE, a 5-SKU simulated policy replay, and measured agent step time rather than an API p95.

## Known limitations

- No lot-level age or expiry. Slow-moving days since last sale use demand rows.
- No separate planned purchase-order date. The calendar shows a stored expected date or says the date is missing.
- Supplier on-time rates are simulated from reconstructed replenishment receipts.
- Category and SKU forecast accuracy are not stored. Performance keeps pooled WAPE.
- Policy replay is a small simulated sample and is not evidence that the multi-agent system beats a simpler policy in general.
- p95 API latency is unmeasured.
- 158 of 200 SKUs needed an upward reconciliation receipt on 2026-11-01.
- The turnover gauge saturates above 12 while the numeric turnover stays exact.
- Power BI screenshot files were not in this workspace.
