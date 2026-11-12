# Phase 15 — Agent Intelligence / orchestration visualization (screenshot 4)

## Design
Use the screenshot as inspiration for an attractive node/edge graph: upstream data at left, independently fitted agents in center, downstream risk agents, final deterministic reorder optimizer on right. Render with lightweight HTML+SVG lines or a small local React graph; do not pull giant graph libs. Include real ten-model list below with model name, fitted method, data source, artifact availability, median/p95 latency if recorded, last run time, key output. Use a right-hand detail inspector.

## Truthful visualization
- Graph is a **dependency DAG**, not actual network messages or LLM 'thinking'. Draw nodes based on one central metadata registry; this same registry powers the orchestrator, tests and UI. No duplicate graph definitions.
- Node execution status must come from actual agent run traces; default `Ready` when fitted, `Unavailable` when not. Only animate a line/nodes while a real triggered run is happening, otherwise show last completed trace snapshot.
- Each agent inspector shows supported metrics only. For quantile outputs display nominal interval coverage, for anomaly show raw score, for supplier/risk show simulated data provenance. **Never use arbitrary 92.3% "confidence" badges** without a clearly defined measurable interpretation.
- Run table: actual trace ID, scenario, invoked agent names, per-agent duration, total duration, status and resulting recommendation; select a run to view its details.
- `Run decision` button invokes a small real on-demand API route. Show spinner and success/error based on actual reply.

## Expected model list
1 demand; 2 demand_interval; 3 intermittence; 4 price_response; 5 calendar_effect; 6 sales_anomaly; 7 product_similarity; 8 supplier_eta; 9 stockout_risk; 10 excess_risk. `Reorder Optimizer` is separately labeled `Deterministic decision engine`, **not** model #11.

## Accessibility + performance
SVG connectors must not obscure node text; graph remains readable at tablet width (overflow scroll allowed) and mobile (vertical stack fallback). Buttons keyboard accessible and inspector toggles respond.

## Acceptance
- Exactly ten model agents available after successful training (quantile pair counts as one agent).
- Selecting a node shows its **actual** metadata, not hardcoded screenshot values.
- Trigger a decision and observe a new trace returned from backend and visible on page.
- Failing or missing model presents honest warning and degraded status.
