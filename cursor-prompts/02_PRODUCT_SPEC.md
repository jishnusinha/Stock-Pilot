# Phase 02 — Product, visual inspection, acceptance contract

## Your job
Inspect every PNG/JPG/WebP in `mockup-ui/`, identify which of five screens it represents, and write `docs/mockup-map.md` with source filename, intended route, layout regions, data needs, and critical interactions. If five screen images are not visible, document their absence and use these feature descriptions; do not block or delete anything.

## Product definition
**StockPilot** is a local-first B2B demo for inventory decisions at one small retailer. It has no LLM or chatbot. Predictions come from trained small traditional ML models and a deterministic optimizer. Display a consistent `Demo data · Simulated supplier/stock outcomes` label where relevant. All monetary values are in INR by default and stored as integer paise (display ₹); no fixed dollar amounts copied from screenshots.

## Pages/routes (required)
- `/` → Command Center: four KPI cards, demand historical/forecast chart with uncertainty band, critical alerts, top risk SKUs, recommended action; links work.
- `/inventory` → Inventory Explorer: product table with search/category/risk/supplier filters, sorting and pagination, selectable product detail drawer with sales graph, stock movements, recommendation, CSV export. Actual filter state is reflected in results.
- `/simulator` → What-If: choose SKU; modify quantity, price, expected lead days and budget; recompute time-series and projected stockout/waste/cost metrics; compare two plans; save, propose and approve an action.
- `/agents` → Agent Intelligence: ten named models, DAG network, run history and selected agent detail with provenance and latency. 'Active' means fitted and available, not continuously running. If a specific metric is not available, show `Not measured`, not an invented percentage.
- `/performance` → Model Performance: verified metrics, temporal backtest chart, strategy comparison, run/model version list; separate forecast results from simulated business outcomes.
- `/reorders` → secondary but functional page showing proposed orders, approve/cancel/status and history. Can use simple table layout.

## Scope exclusions
No payments, real supplier purchase APIs, multi-tenant auth, email, cloud deploy, mobile native apps, human customer financial data, live POS integrations, real M5 dependency, fake AI conversational answers, or automated ordering external goods.

## Design system
- Warm ivory/off-white background, charcoal typography, emerald primary/soft mint surfaces, subtle blue secondary series, amber/red risk labels, border radius ~12–16px, lightly stroked white cards.
- Desktop composition: ~220px left sidebar, top header with search and demo store/account, main grid with KPI cards and large charts. Responsive at 1440px, 1024px and 390px.
- Carefully replicate reference hierarchy/spacing and content density; don't paste screenshots as page backgrounds. Use Lucide icons, CSS, Recharts. Minimal decorative motion. No fake upgrade/billing button; replace sidebar promotion with a helpful Demo Mode / ML status panel.
- Every displayed UI number from API or derived front-end from API response. Type definitions must align with backend Pydantic models. Loading, empty/error, and stale-state handling required.

## UX flows to prove
1. Open command center → inspect alert → open relevant product in inventory.
2. Search/filter SKU → open product details → record a stock adjustment → see updated counts and movement record.
3. Select SKU → adjust reorder slider → see recomputed scenario and chart → save scenario → request reorder → approve on Reorders page → see database persistence.
4. Open Agents → inspect actual trace and every agent metadata/model outputs.
5. Open Performance → inspect genuine backtest comparisons and see data source disclosures.

## Deliverable / check
`docs/mockup-map.md` and `docs/product-contract.md` listing routes, flows, provenance rules and explicit no-LLM statement. Add checklist to PROGRESS. Nothing is marked done until images have been inspected and descriptions mapped.
