# UI v2 audit

Visual source of truth: the five files in `mockup-ui/` (not modified). Monetary figures in those images are illustrative USD. The app stores paise and displays INR. SKU counts in the images (for example 2,748) are not used; the seeded catalog is 200 products. No KPI in the UI is copied from the mockups.

## Shared chrome

| Mockup | Current before this pass | Gap |
|---|---|---|
| Ivory canvas, white cards, emerald active nav, brand mark | Functional sidebar and top bar with inline styles | Weak elevation, system font, decorative bell, no compact nav, menu button logic was a one-off style tag |
| Search, alerts, Summit Retail identity | Search navigated to inventory; bell did nothing | Alerts must come from `/api/dashboard`, not invented events |
| Upgrade card | Correctly replaced by demo/ML status | Keep that replacement |

Checklist: design tokens, shared shell, real notification panel, compact sidebar, mobile drawer, toast system, focus states.

## Command Center — `d6b91902-d4f3-47b4-a1ec-31e6dbac263c.png` — `/`

Layout: header, four KPI cards, large forecast, alerts, recommendation, risk table.

| Region | Before | Discrepancy |
|---|---|---|
| KPIs | Plain cards; trends often null | Need icon hierarchy. Do not invent trend percents when the API sends null. Savings must stay labeled as a simulation. |
| Forecast | p10 and p90 drawn as two stacked areas | Band could paint the wrong interval. Rebuild as one span from p10 to p90. |
| Alerts / recommendation | Present, visually flat | Match severity styling and make the reorder action obvious. |
| Risk table | Basic columns | Add cover meter and category. Row opens the product. |

Checklist: honest KPIs, corrected band, history window over real series only, alerts and draft reorder still call the API.

## Inventory Explorer — `68b663be-7609-4e9e-8fe0-56066af58f74.png` — `/inventory`

| Region | Before | Discrepancy |
|---|---|---|
| KPIs | Page, page size, filter count | Replace with catalog-wide total, low stock, overstock, average days of supply. |
| Categories | Built from the current page | Load the full category list. |
| Sort | `dir` stored in the URL but not sent | Pass `direction` to the API. |
| Table / drawer | Usable, sparse | Product/SKU hierarchy, cover meter, forecast column, accessible drawer. |

Checklist: summary endpoint, sort direction, stock-health filter, preserve create/edit/delete/adjust/export.

## What-If Simulator — `1457518b-16f6-4998-9f5c-4739a9e5d39b.png` — `/simulator`

| Region | Before | Discrepancy |
|---|---|---|
| Layout | Form above a chart | Three-column decision lab on desktop. |
| Chart | Two lines | Add stockout reference at 0 and the API arrival date. Do not draw a confidence band on deterministic paths. |
| Scenarios | Save only, `alert()` | Reopen via scenario detail. Compare stored results only when they were saved. |
| Copy | Some observational labeling | Keep the non-causal price note visible. |

Checklist: sliders recompute `/api/simulate`, save, reopen, draft reorder.

## Agent Intelligence — `c0627307-626a-4f95-bf0c-505f3039cf28.png` — `/agents`

| Region | Before | Discrepancy |
|---|---|---|
| Graph | Fixed SVG with incorrect edges (demand feeding price, a fake data node) | Redraw from orchestrator dependencies only. |
| KPIs | Count of agents | Do not invent confidence, decision counts, or savings. |
| Inspector / traces | Definition list and a bullet list | Node inspector plus duration waterfall from the trace payload. |

Checklist: 10 agents + optimizer, selectable path highlight, trigger run, no fabricated accuracy.

## Model Performance — `1c33fd0b-6386-40f5-b70c-bb9ae3e7cacd.png` — `/performance`

| Region | Before | Discrepancy |
|---|---|---|
| KPIs | Text metrics | Keep WAPE, MAE, coverage, latency. p95 stays "Not measured" unless the API measures it. |
| Comparison | HTML table | Bar chart of measured WAPE. Do not declare an ML win. |
| Backtest | Two lines | Label rolling one-step versus multi-horizon. |
| Business block | Cost table | Chart defined cost. Do not relabel it as savings. |
| Registry | Flat table | Filter the registry client-side. Do not invent version history the API does not return. |

## Reorders and settings

No dedicated mockup. The nav item exists. Build status summary, tabs, detail, confirmations, and toasts without changing the approve-does-not-increment-stock rule.

## Explicit non-goals from the images

Units/revenue toggle, fake 12-week confidence, upgrade plan, illustrative USD, sell-through percents (the cache field `sell_through` is a daily demand figure, so it is not shown as a rate), and any accuracy or savings number that is not in an API payload.
