# Phase 12 — Command Center (screenshot 1)

## Goal
Replicate the Command Center screenshot in `mockup-ui/` as a working responsive, API-driven page. Use its information hierarchy: large page title/subtitle, top four KPI cards, left big demand chart, right alerts/recommendation cards, bottom top-risk table.

## Components
- Four KPI cards derived from `/api/dashboard`: projected revenue, at-risk products, suggested reorders, estimated savings. If evidence insufficient for `savings`, show "Simulation estimate" or `N/A`, not an invented ₹ figure.
- Demand history + forecast line using Recharts: actual series, p50 future and p10–p90 interval. Show a visible split between historical and forecast; label nominal 80% interval where model uses p10/p90.
- Critical alerts list with risk severity and links that open relevant SKU detail; UI picks latest forecast snapshot instead of static dates.
- Recommendation panel with generated template explanation and `Review reorder` button that creates/views a draft through API. No external purchase is placed.
- Top products at risk table with category/SKU/stocks/days of supply/forecast/risk badges; clicking a row navigates to `/inventory` and selects relevant item.
- Date range controls show options only if backed by actual API data, otherwise hide/disable with explanation.

## Data flow
Build one `useEffect` or custom data hook calling `/api/dashboard`, retry/refresh button, skeleton/empty/error state. Refetch after stock movements and reorder actions (route navigation or refresh), not hardcoded duplication.

## Acceptance
- Seeded demo renders nonempty KPIs, alerts, 28-day plot, risk list.
- Every click leads to working route or action.
- Forecast charts and product data consistently match current SQLite state and model cache.
- No misleading "AI" chat text: call this `ML recommendation` or `StockPilot recommendation`.
