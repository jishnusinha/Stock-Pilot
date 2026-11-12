# UI v2 verification

Date: 2026-11-12. Local Windows machine. No commits were created.

## Screens redesigned

Command Center, Inventory Explorer, What-If Simulator, Agent Intelligence, Model Performance, Reorders, and Settings. Shared sidebar and top bar.

## Components

Reused and restyled `AppShell`, `Sidebar`, `Topbar`, `KpiCard`, `DataTable`, `Badge`, `ConfirmDialog`, `ProductDetailDrawer`, `ProvenancePill`. Added `Toast`, `PageHeader`, `ProgressBar`, `SegmentedControl`, `SliderControl`, `AgentGraph`, and `TablePagination`.

## Behavior that changed

- Product sort sends `direction=asc|desc`. Category options come from the catalog summary, not the current page.
- Inventory KPIs are catalog-wide: on the seeded database they were **200 SKUs**, **109 low stock** (high risk or ≤ 14 days of supply), **10 overstocked** (≥ 90 days), **average cover 24.8 days**.
- Forecast uncertainty is one interval: base at p10, height `max(0, p90 − p10)`. Historical points are not given a band.
- Saved scenarios can be reopened from `GET /api/scenarios/{id}`.
- The agent graph uses the orchestrator edges, including anomaly and similarity into demand, and demand plus supplier ETA into the optimizer. There is no fake "data" model node.
- Notification count is the dashboard alert list (3 alerts on this database). The bell opens those alerts.
- Browser `alert()` calls in the redesigned screens were replaced with toasts and confirmation dialogs.

## Backend

- `GET /api/inventory/summary`
- `GET /api/products` accepts `direction` and `stock_health` (`low` or `overstock`)
- `GET /api/scenarios/{id}` returns stored inputs and results
- `DAG_EDGES` matches the orchestrator signal flow
- Product page size cap raised to 250 so the simulator can load the 200-SKU catalog

## Dependencies

Frontend devDependencies: `vitest@2.1.9`, `jsdom@25.0.1`, `@testing-library/react@16.1.0`, `@testing-library/dom@10.4.0`. Inter is loaded from Google Fonts with a system-font fallback. No new runtime production dependency.

## Tests executed

```text
backend: .venv\Scripts\python -m pytest -q
40 passed, 7 warnings in 30.78s

frontend: npm test
6 passed (forecast band, product query direction, orchestration path, sidebar routes)

frontend: npm run build
tsc --noEmit && vite build succeeded
```

## Browser verification

API was already running on port 8000. Vite was restarted on http://127.0.0.1:5173 after the Vitest config change had stopped the previous dev server.

Checked in the IDE browser with an emulated 1440×900 viewport and a 390×844 viewport:

| Route | Result |
|---|---|
| `/` | Title, four KPIs (₹26,98,240 projected revenue, 58 at-risk, 199 recommendations, ₹65,603 simulated impact), forecast chart, 3 alerts. No console errors. |
| `/inventory` | Summary KPIs matched `/api/inventory/summary`. 20 rows, full category list, 8 suppliers. Opening a row showed the product drawer; Escape closed it. |
| `/simulator` | 200 products in the picker. Simulation returned revenue, stockout probability, purchase cost, and a chart. |
| `/agents` | 10/10 artifacts, 11 graph nodes, demand inspector text, 19 traces. |
| `/performance` | WAPE 29.0%, MAE 2.293, p95 "Not measured", multi-agent defined cost ₹183 labeled as holding plus shortage, not savings. |
| `/reorders` | 3 received orders, status tabs, stock-once copy. |
| `/settings` | Rendered. |

At 390px, document scroll width stayed within the viewport on these routes after the agent graph was constrained to scroll inside its card. The mobile menu button is shown and the sidebar starts off-canvas.

Screenshots taken through the IDE browser were cropped to the visible panel, so they were not used as a full-layout comparison against the mockups. Layout measurements above are from the emulated viewports.

## Known limitations

- KPI trend arrows from the mockups are omitted when the API sends null. Savings remain a simulation label.
- `sell_through` in the risk cache is a daily demand figure, so it is not shown as a sell-through percentage.
- p95 latency is not measured.
- Price response is observational, and the simulator says so.
- Approving a reorder does not increase stock. Receiving does, once. That backend rule was not changed.
- Inter will not load if the machine is offline; the UI falls back to the system font.
