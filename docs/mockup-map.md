# Mockup map

Source of visual truth: `mockup-ui/` (never modify). Monetary mockup values are illustrative USD; app uses **INR (paise storage)**. Screenshot SKU counts (e.g. 2,748) are replaced by seeded **200 SKUs**.

| File | Screen | Route | Layout regions | Data needs | Critical interactions |
|---|---|---|---|---|---|
| `d6b91902-d4f3-47b4-a1ec-31e6dbac263c.png` | Command Center | `/` | Sidebar, top search, 4 KPI cards, demand forecast chart, top risk table, critical alerts, recommendation card, insight summary | `/api/dashboard` KPIs, forecast series, alerts, risk SKUs, recommendation | Alert → inventory; Create Reorder; View details |
| `68b663be-7609-4e9e-8fe0-56066af58f74.png` | Inventory Explorer | `/inventory` | KPI strip, filterable table, product detail drawer (overview/sales/history) | `/api/products`, detail, adjust-stock, export.csv | Search/filter/sort/page; open drawer; adjust stock; export CSV; create reorder |
| `1457518b-16f6-4998-9f5c-4739a9e5d39b.png` | What-If Simulator | `/simulator` | 4 impact KPIs, sliders, inventory path chart, outcomes table, plan compare, apply/save | `/api/simulate`, `/api/scenarios`, propose reorder | Sliders recompute; save scenario; apply → draft reorder |
| `c0627307-626a-4f95-bf0c-505f3039cf28.png` | Agent Intelligence | `/agents` | Agent KPIs, DAG panel, agent cards, recent runs, agent detail | `/api/agents`, `/api/agent-runs`, trigger | Select agent; inspect trace; trigger on-demand run |
| `1c33fd0b-6386-40f5-b70c-bb9ae3e7cacd.png` | Model Performance | `/performance` | Metric KPIs, model comparison, backtest chart, versions table, business simulation | `/api/performance` | Filter model family; inspect measured vs simulated labels |

## Shared chrome
- Left sidebar (~220px): brand, nav, Demo Mode / ML status panel (replaces Upgrade CTA).
- Top bar: search, notifications, Summit Retail Co. demo identity.
- Palette: warm ivory `#FAF9F6`, charcoal `#1B2520`, emerald `#096B3B`, mint `#E7F5E8`, borders `#E4E7E1`.

## Secondary routes
- `/reorders` — pending/approved/rejected/received (functional table; mockup nav item).
- `/forecast` → redirect `/` or `/performance`; `/products` → `/inventory`; `/suppliers` → inventory supplier filter; `/reports` → `/performance`; `/settings` → demo info panel.
