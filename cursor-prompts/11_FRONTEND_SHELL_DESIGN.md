# Phase 11 — Frontend foundation + visual design system

## Read the mockups
Look at `mockup-ui/` and `docs/mockup-map.md` before writing CSS. Build the same family of pages using **real React components**, not embedded screenshots. Inspect reference visual layout, card proportions, table density, heading type, palette, spacing and responsive behavior.

## Bootstrap
Vite React TS app under `frontend/`; React Router with routes: `/`, `/inventory`, `/simulator`, `/agents`, `/performance`, `/reorders`; not-found redirect/404; `/products/:id` may redirect to inventory open drawer. `src/api/client.ts` with typed `fetch`, response validation or robust error handling, `VITE_API_URL` env and abort support; do not tightly couple UI to backend internals.

## UI design tokens
- Colors: warm `#FAF9F6` page, charcoal `#1B2520` foreground, dark emerald `#096B3B` primary, mint `#E7F5E8`, borders `#E4E7E1`, cool blue forecast, orange warning, red risk.
- White/offwhite cards with border and subtle shadow, radius 12–16px, generous 16–28px gaps, responsive CSS grid and flex.
- Typography: system-font stack with crisp headings, tabular digits on metrics; optional safe Google fonts **not required** (app must work offline).
- Icons `lucide-react` and charts Recharts. Avoid large animation frameworks; use CSS transitions, reduced-motion support.
- Persistent responsive sidebar, search bar and demo identity badge; show "Demo Mode / Synthetic Retail Dataset". Replace screenshot "Upgrade Plan" upsell with demo-state or model-health panel.

## Reusable components
`AppShell`, `Sidebar`, `Topbar`, `KpiCard`, `Badge`, `DataTable`, `EmptyState`, `ErrorState`, `Skeleton`, `LoadingOverlay`, `DateRangeLabel`, `ChartCard`, `ProductDetailDrawer`, `ConfirmDialog`, `Toast/Alert`, `ProvenancePill`, `ResponsiveLegend`.

## Functional accessibility
Buttons and links need hover/focus/keyboard behavior. Label inputs/sliders; dialogs trap focus or use native `<dialog>` appropriately; charts must have text alternatives. Responsive 1440px, 1024px, 390px (collapse sidebar, scroll table horizontally). No dead buttons. Keep page count narrow and purposeful.

## Contract
Add `src/types/api.ts` with API types (derive from documented Pydantic schemas). Provide central date/INR format helpers, and a network error banner; no hardcoded revenue metrics, dollar signs or screenshot stock values.

## Acceptance
`npm run build` must pass with TypeScript strict checks; app shell renders without backend (clear connection error state), main nav routes change correctly, screenshot fidelity obvious when side-by-side visually compared.
