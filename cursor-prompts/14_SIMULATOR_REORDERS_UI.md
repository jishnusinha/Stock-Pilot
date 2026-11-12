# Phase 14 — What-If Simulator and real reorder approval (screenshot 3)

## Visual anatomy
Follow the What-If screenshot: product picker at top, 4 KPI comparison cards, left controls, large projected inventory chart, lower side-by-side outcome table, right recommendation and action buttons. Add plain currency/provenance labels.

## Inputs and meaning
- SKU selection from existing products.
- Proposed reorder quantity `q`, in pack-size increments, default to model optimizer suggestion.
- Proposed selling price (integer paise input displayed INR); bounded around product's baseline price.
- Supplier lead time in days; slider changes scenario expected delivery, **not** the authoritative supplier profile.
- Purchase budget in INR; proposed `q * unit_cost` must be <= budget. Disabled Apply when invalid.
- Duration 28 days by default; baselines are current plan (`no new order` or persisted approved order) vs proposal; label exactly which baseline used.

## Behavior
`POST /api/simulate` returns hypothetical daily inventory paths and comparable projected metrics for both plans (stockout days / unmet demand, probability estimate, excess risk, purchase cost, revenue, gross margin) derived using same simulator random seed. Debounce requests (300–400ms), cancel in-flight request when inputs change, show pending state. Do not fake live inference streaming or produce nonresponsive sliders.

`Save Scenario` posts exact values/outputs to `/api/scenarios` and reports success; optionally list last saved scenarios. `Create Draft Reorder` posts recommendation/proposal (or `/api/reorders` draft route if API contract updated coherently). Redirect to `/reorders` where Approve, Reject and Receive work with persistence. Approval is **not** a real external supplier order, and only Receive modifies stock on hand.

## Validation edge cases
- q=0, no budget, insufficient budget, long lead time, no supplier, perishable shelf-life, predicted stockout before arrival, all-zero/uncertain demand.
- Display `N/A` rather than infinity/NaN on no revenue or denominator zero.
- If models unavailable, disable decision feature with helpful bootstrap instructions; don't silently use screenshot placeholder numbers.

## Acceptance
- Changing **each** slider alters expected appropriate graph or metric (unless logically no impact; clearly label when not relevant).
- Proposed arrival manifests at chosen lead-day date, not immediately.
- Saved scenario survives reload.
- Draft → Approved → Received transition persists and affects inventory exactly once, rejection does not.
- Displayed scenario formula/provenance agrees with `docs/model-methods.md`.
