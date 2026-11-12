# 4-minute live demo script

**Assumptions:** Demo Mode, snapshot `2026-11-01`, synthetic retailer, INR, no LLM.

1. **Command Center** — Open `/`. Point at at-risk KPI and critical alert. Note provenance pill. Click alert → Inventory.
2. **Inventory** — Filter High risk. Open a SKU drawer. Adjust stock by +5; show movement history. Export CSV briefly.
3. **Simulator** — Same SKU. Move reorder qty slider; chart/metrics recompute. Save scenario. Apply → draft reorder.
4. **Reorders** — Approve (stock unchanged). Receive (stock increases once).
5. **Agents** — Show 10 fitted agents + DAG. Trigger on-demand run; open real trace timings.
6. **Performance** — Holdout WAPE vs baselines; business block labeled SIMULATED.

Close with: “All local, SQLite + sklearn, no cloud keys.”
