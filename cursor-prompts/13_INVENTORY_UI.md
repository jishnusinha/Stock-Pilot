# Phase 13 — Inventory Explorer + product details (screenshot 2)

## Screen anatomy
Implement Inventory Explorer from `mockup-ui/`: page heading, 4 small summary cards, filters row with search/category/risk/supplier, product table, right detail drawer/panel. Use clean risk colors, compact row density, selected-row treatment, trend chart and reorder recommendation panel.

## Required interactions
- Search SKU/name with debounce (250–350ms), category/risk/supplier filters, sort, page size, server-driven pagination and total count; URL query-state preferred for sharable views.
- Select row: detail panel loads `GET /api/products/{id}` with product, 30-day historical sales chart, 28-day forecast, reorder recommendation, supplier + lead-time, movement history. Close drawer or change selection by keyboard.
- `Adjust stock`: small modal with signed quantity, reason and confirm. Calls POST adjust-stock; after success invalidate product/dashboard/forecast-related cached decisions (or mark stale with a refresh button). Demonstrate DB persistence.
- Export CSV: download exactly the filtered results via API (not a placeholder).
- Sorting accessible with indicators and named directions. No broken tabs: Overview, Sales & Demand, History display distinct real content.
- `Review reorder` creates draft or navigates with selected item to simulator; never silently places a real order.

## Performance
No client-side rendering of entire 73K sales rows; server returns paginated products, detail endpoints only limited ranges. Recharts graphs on at most ~90 points per chart.

## Acceptance
Filters affect server results and table; row detail values match API; stock changes persist after browser reload; CSV has product rows and headers; empty filter state looks polished.
