# UI v2 progress

Updated after implementation and verification on 2026-11-12.

| Phase | Status | Evidence |
|---|---|---|
| 1 Design system | Done | `tokens.css`, `layout.css`, `components.css`; shared shell, cards, tables, badges, toasts |
| 2 Application shell | Done | Sidebar with compact mode and ML/database status; top bar search, real alert panel, demo menu |
| 3 Command Center | Done | KPI cards from `/api/dashboard`; p10–p90 drawn as one band; alerts and draft reorder |
| 4 Inventory Explorer | Done | Catalog summary endpoint; sort `direction`; full category list; drawer, adjust, export kept |
| 5 What-If Simulator | Done | Sliders recompute `/api/simulate`; scenarios reopen from `GET /api/scenarios/{id}` |
| 6 Agent Intelligence | Done | 11-node graph aligned with orchestrator edges; inspector; trace waterfall; run decision |
| 7 Model Performance | Done | Measured WAPE/MAE/coverage; p95 stays "Not measured"; policy cost is not labeled as savings |
| 8 Reorders | Done | Status tabs, purchase totals, detail, confirmations. Approve still does not change stock |
| 9 UX polish | Done | Toasts replace `alert()`; confirm dialogs; Escape closes the product drawer |
| 10 Responsive | Done | Checked at 1440 and 390. Agent graph scrolls inside its panel instead of widening the page |
| 11 API | Done | `direction`, `stock_health`, `/api/inventory/summary`, scenario detail, corrected DAG edges |
| 12 Tests | Done | Backend `40 passed`. Frontend `6 passed`. `npm run build` succeeded |
| 13 Docs | Done | This file, `docs/ui-v2-audit.md`, `docs/ui-v2-verification.md` |

## Not done / limits

- No pixel-perfect copy of mockup USD figures or fake trends.
- p95 latency is still unmeasured.
- Browser screenshots of the IDE panel were cropped; layout checks used a 1440×900 and 390×844 emulated viewport.
