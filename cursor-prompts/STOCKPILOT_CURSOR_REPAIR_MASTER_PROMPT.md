# StockPilot — Local Completion, ML Correctness & MLOps Hardening

You are acting as a **senior ML engineer, MLOps engineer, backend engineer, frontend engineer, QA engineer, and technical reviewer** in this existing StockPilot repository. Your job is **to implement, repair, test, and verify** the project on this local machine, not merely to describe solutions. Work autonomously, in phases, within the available context and tool permissions. Continue through the phases without waiting for approval for ordinary non-destructive changes. Never claim a check passed unless you actually ran it.

## Mission and non-negotiable constraints

- **Preserve and improve the existing implementation. DO NOT rebuild the application from scratch.** Start by inspecting what is currently present; repository contents may have changed since the audit below.
- Project: **StockPilot**, a local-first synthetic retail inventory intelligence app with React + TypeScript + Vite frontend, FastAPI backend, SQLite database, ten specialized scikit-learn ML agents, dependency-aware orchestration, and deterministic reorder optimization. **No LLM**.
- Hardware: **8 GB total RAM, ~7 GB free disk, CPU-only**. Use at most two training threads, sequential training, compact models, carefully managed memory, existing environments where possible, and `pip --no-cache-dir` if new dependencies are genuinely needed. Avoid Docker, GPU, TensorFlow, PyTorch, Kubernetes, Redis, PostgreSQL, cloud services, and major new dependencies.
- The repository already includes five design references in `mockup-ui/`. Preserve these and the existing look, routes, responsiveness, branding and user workflows. The UI must remain API-backed; no fabricated metrics or hardcoded screenshot values.
- Do **not** reset, delete, replace, or overwrite a populated SQLite database, model artifact directory, user data, `.env`, or uncommitted changes. Inspect `git status` first. Back up local data before a migration or a destructive test. Use **isolated temporary DBs** for automated tests. Do not push to GitHub or deploy to AWS without explicit authorization.
- Keep local-first operation completely functional without AWS, external API keys, Kaggle access or an internet connection after ordinary dependencies are installed.
- Distinguish clearly between `SYNTHETIC_DEMO` sales, `SIMULATED_SUPPLY` labels and outcomes, measured backtest results, measured performance, and unknown/unmeasured metrics. Do not call predicted purchasing spend “savings”. Do not label training metrics as independent holdout metrics.
- Any ML improvement must be backed by a **repeatable test or evaluation**. Do not promise that multi-agent will outperform a simpler model: report the real measured outcome, even if worse.
- Current project commands should remain usable. Minimize breaking API schema changes; update backend, frontend, tests, documentation and migrations together when necessary.

## Start by reading the repository and establishing a baseline

1. Inspect `git status`, branch, project tree, README, `cursor-prompts/PROGRESS.md`, existing `docs/`, five mockups, Python package versions, frontend package scripts, tests, CLI and start scripts.
2. Specifically inspect these files (or their current equivalents):
   - `backend/app/ml/{features,splits,backtest,metrics}.py`
   - `backend/app/agents/{demand,demand_interval,price_response,calendar_effect,sim_supply,stockout_risk,excess_risk,supplier_eta}.py`
   - `backend/app/services/{orchestrator,reorder_optimizer,scenarios,simulate_api,bootstrap,performance}.py`
   - `backend/app/api/{routes,schemas}.py`, `backend/app/db/{migrations,repositories,connection}.py`
   - `frontend/src/pages/{CommandCenter,Inventory,Simulator,Agents,Performance,Reorders}.tsx`
   - `backend/tests/`, `scripts/`, `frontend/src/api/`, `frontend/src/types/`.
3. Run existing verification **before editing** if dependencies are available: backend `python -m pytest -q`, frontend `npm run build`, `python -m app.cli model-status`, and a local API health smoke check if the API is already up. Record results without pretending unavailable commands succeeded.
4. Write `cursor-prompts/REPAIR_PROGRESS.md` containing: initial git SHA/status, actual baseline outcomes, phase checklist, changes made, commands run, measured results, unresolved issues, and exact continuation instructions. Update it after every phase. Do not mark a phase complete without its acceptance checks.
5. If the repository already fixed an issue, verify it and mark it as already resolved instead of rewriting working code.

## Known audit findings to CONFIRM against current code

At the previously inspected `master` revision, these were concrete problems:

A. **Invalid demand holdout evaluation** in `backend/app/ml/backtest.py`: demand-only prediction is made using all available data, then a single prediction is compared repeatedly with **mean holdout demand**, instead of historically valid point-in-time daily actuals. Reported WAPE around 0.057 must be considered untrustworthy until corrected.

B. **Risk-classifier leakage** in `backend/app/agents/sim_supply.py`: training features included `stockout_days`, `excess_peak`, and `spoil_risk`, which are generated from the simulated future and directly determine labels. Inference uses placeholder zeros for those features. This is target leakage plus training-serving skew.

C. **Optimizer candidate-independence:** `backend/app/services/reorder_optimizer.py` adds the same `stockout_risk` / `excess_risk` penalty to every candidate quantity. Consequently these predictions cannot alter the selected quantity. `max_packs = max(1, ...)` can permit an unaffordable pack.

D. **Price what-if is not connected to forecast demand:** `simulate_api.py` forwards proposed price to the demand agent but the previously inspected `DemandAgent.predict_one()` ignored it. `PriceResponseAgent` returned a raw predicted level called `expected_units_delta`, which is misleading if not computed as a difference from a baseline prediction.

E. **Flat forecast horizon:** demand point and p10/p90 are repeated for every one of the next 28 days, without properly accounting for future dates, lag recursion and forecasting horizon.

F. **Weak actual downstream collaboration:** upstream calendar/price/intermittence/anomaly/similarity results are logged but are not necessarily consumed in trained downstream inference. A displayed DAG is not proof of actual signal dependence.

G. **Incomplete model-performance data:** `/api/performance` returned `backtest_series: []`, missing observed interval coverage and missing measured p95 latency; suggested purchase cost was shown in the business section but is not realized savings.

H. **Sparse regression coverage:** existing tests mainly checked happy paths and pack multiples, not budget = 0, affordable-pack boundaries, leakage, price sensitivity, backtest correctness, state refresh, and objective-function behavior.

I. **Potential stale state:** changing inventory or approving/receiving orders must invalidate or refresh affected risk cache and recommendation state, or clearly mark it stale. A draft order must not increment physical stock; receive exactly once should.

J. **Local MLOps and quality gaps:** no confirmed frontend interaction suite or automated GitHub CI; Linux/macOS scripts not verified; need better model metadata / version compatibility, ablation evaluation, reproducibility and local operational documentation.

## Phase 1 — Correct temporal ML evaluation (P0)

Implement a valid **walk-forward / rolling-origin** evaluation for demand forecasting. Train ONLY using observations available before each evaluation origin. Construct inference features using only information available at the origin. For one-day-ahead tests, using prior observed holdout history is acceptable **only** if clearly labeled as rolling one-step evaluation. For true 7/14/28-day-ahead evaluation, do not use future observed holdout sales as recursive lag values. Use recursive predictions or a properly trained direct multi-horizon approach; either is acceptable if correct and efficient.

- Build aligned actual-vs-predicted records by `{product_id, forecast_origin, target_date, horizon, actual, prediction, model_version, provenance}`.
- Evaluate baseline seasonal naive, moving average, and the demand model on the **same dates, SKUs, and horizons**. Report WAPE, MAE, RMSE, sample sizes and data window; guard against zero-demand denominators.
- Maintain proper train / validation / untouched test separation; avoid using test for tuning. For small synthetic data, do a small number of origins rather than massive retraining.
- Add focused tests proving evaluation does not read future data, backtest actuals are genuine daily observations (not group means), dates align, and leakage-prevention remains valid.
- Replace misleading prior metrics on the Performance screen with newly verified results. Don't silently preserve the old 5.7% claim.

**Exit criteria:** time-valid backtest produces nonempty actual-vs-predicted series, aligns observations and predictions, and tests catch intentional leakage.

## Phase 2 — Rebuild both risk classifiers correctly (P0)

- Redesign the simulator to distinguish **decision-time inputs** (stock, reorder point, pack size, demand estimate/uncertainty, lead-time estimate, proposed quantity, shelf life, etc.) from **future-only outcomes** (realized stockout days, excess peak, spoilage). Training X must include **only decision-time values**; labels y are derived solely from later simulated paths.
- Use a single shared, versioned feature schema for fit and predict, including exact name/order and transformations. Validate correct dimensions and reject unknown/missing feature mismatches instead of quietly using arbitrary zeros.
- Split simulated data by scenario groups and/or product and seeds to avoid train/evaluation overlap. Include probability calibration or at minimum compute properly independent Brier score plus precision, recall, PR-AUC or ROC-AUC when feasible.
- Add tests for data leakage, schema consistency, probability bounds, sensible direction under controlled scenarios (e.g., increasing available stock/order should not systematically increase stockout risk when all else is fixed), and independent evaluation.
- Clearly label `SIMULATED_SUPPLY` results on API/UI. Report uncertainty/limitations.

**Exit criteria:** no future-only training inputs; reliable, correctly evaluated probabilities; consistent inference schema.

## Phase 3 — Correct optimization and business accounting (P0)

- Candidate quantities must be **zero or nonnegative pack multiples** whose purchase cost does not exceed budget; `budget=0` or budget less than one pack cost must permit only zero. Never force one pack via `max(1, ...)`.
- Recompute candidate-specific expected shortage, holding, excess, and spoilage costs from the **candidate's simulated trajectory** and/or appropriately candidate-conditioned risk predictions. If a risk probability affects the objective, it must vary by candidate or be used explicitly as a true constraint. No constant candidate-invariant “risk penalties”.
- Use a transparent dimensionally consistent cost formulation. Purchasing cash outlay is not equivalent to economic loss; calculate inventory holding, lost-margin or shortage penalty, spoilage, and cost of goods sold separately. Explain assumptions and units. Avoid double-counting inventory acquisition and COGS.
- Define ordering within the lead time and 28-day horizon unambiguously. Track unmet demand units, not only a boolean number of stockout days; handle late arrivals and inventory clipping consistently.
- Make the result deterministic under a fixed seed. For uncertainty-aware optimization, evaluate candidates on the **same sampled demand/lead-time paths** for a fair comparison, with a bounded candidate count that works on CPU.
- Add tests: zero budget, under-pack budget, pack multiples, min/max quantity, zero demand, stock > forecast demand, long lead time, shelf life, repeated call determinism, candidate risk influencing decisions, and objective selection against an independent small brute-force oracle.

**Exit criteria:** all recommendations obey hard constraints, objective is explainable, and optimizer's selected quantity minimizes the defined score over feasible candidates.

## Phase 4 — Make the ten agents contribute meaningfully (P0)

- Audit each agent's `fit`, `predict_one`, source data, output semantics, feature schema, downstream consumer, and whether it is really a fitted model. Create/update `docs/agent-dependency-contract.md` as a table: `agent -> inputs -> outputs -> trained on -> consumer -> effect on decisions -> validation`.
- Implement actual downstream consumption for applicable upstream signals rather than simply logging them. For example: learned calendar / price response can condition future demand where validated; intermittence can adjust zero-demand likelihood; anomaly findings can trigger a conservative fallback or uncertainty widening; supplier ETA affects arrival; product similarity can support sparse-data fallback; demand intervals influence risk/optimization. If an agent's signal does not improve quality, say so and do not claim it does.
- Use deterministic, explicit dependency ordering (a DAG). Skip agents not required for a request. Capture each node's status, version, duration, inputs (non-sensitive summary), outputs, and errors.
- Failed or missing agents should produce explicit fallback provenance and visible notices; avoid broad `except Exception: pass` masking failures. Prevent partial silent success or fabricated 10/10 completion.
- Add graph contract tests: topological order, dependency injection, partial failure, repeatable outputs and scenario sensitivity.

**Exit criteria:** at least one downstream business decision measurably changes because of genuine upstream ML signals; the trace proves the actual dataflow.

## Phase 5 — Make the What-If Simulator mathematically consistent (P0)

- Scenario changes to **price** must affect expected units if there is a valid, trained price-response estimate, not just `forecast revenue = old units × new price`. Compute a **difference from baseline** and constrain implausible response. Do not claim causal price elasticity from observational/synthetic data. If effect is unidentifiable, transparently mark price effect as illustrative/disabled rather than showing misleading precision.
- Reorder quantity, lead time, and budget must all change the relevant inventory path and risk projections consistently. Validate or explicitly normalize pack-size multiples **after** budgeting, and return `requested_qty`, `applied_qty`, and an explanation if changed. Frontend must show the applied quantity; creating a draft must use the applied feasible quantity.
- Avoid calling `revenue - purchase spend` “gross margin” or profit. Use fulfilled units × selling price for revenue, fulfilled units × unit acquisition cost for COGS (with appropriate inventory assumptions), then gross margin; separately report cash spent and estimated holding/lost-sales penalties.
- Baseline and proposed strategies must use the same horizon, assumptions, and comparable sampled outcomes.
- Add tests that proposed-price change affects forecast demand when an identified signal is present, lead-time changes arrival/shortage outcomes, budget/pack normalization stays feasible, and scenario results are internally coherent.

**Exit criteria:** sliders and actions correspond to mathematically meaningful, test-verified changes; UI labels do not overclaim.

## Phase 6 — Build honest model and policy evaluation (P1)

- Implement a reproducible inventory replay comparing **(a) fixed rule**, **(b) demand-only forecast + reorder**, and **(c) multi-agent decision system** on identical simulated demand/lead-time sequences. Avoid future leakage and unfair differing initial inventory or exogenous randomness.
- Report per-policy stockout days, unmet demand units, order units, average inventory, holding cost, spoilage cost, shortage penalty, purchasing cash outlay, COGS, revenue, and total defined cost. Report absolute and relative differences **only if measured**. If multi-agent underperforms, show that truth and discuss tradeoffs.
- Run **ablation tests**: remove one upstream signal / risk module and compare decision metrics; note when each agent adds no measurable value.
- Provide nonempty valid backtest chart data. Empirical interval coverage and pinball loss must be out-of-sample; display `N/A` if not actually evaluated. Calculate p50/p95 latency from enough real timing samples, with sample count and measurement context; otherwise show `Not measured`.
- Persist evaluation metadata (seed, snapshot date, training/testing windows, model versions, baseline definitions) and display in `Performance.tsx`.
- Make tests assert no fabricated metrics, correct monetary units, nonempty series, and independently reproducible replay results.

**Exit criteria:** Performance screen reports transparent, reproducible metrics and policy comparisons, not invented savings.

## Phase 7 — Data integrity, backend behavior and operational safety (P1)

- Audit SQLite migrations and repository methods. Keep every data mutation transactional and preserve foreign keys. Maintain robust reorder status transitions: `pending -> approved -> received`, and `pending -> rejected`; receiving should increment stock **once** even under duplicate requests. Prevent zero-quantity or unfunded draft orders where required.
- After stock adjustments, product changes, receiving stock, or changing a relevant business input, invalidate or refresh stale risk/recommendations and expose `updated_at/as_of` to the UI. Avoid stale or contradictory numbers across Command Center, Inventory and Simulator.
- Add parameter validation, sane pagination, consistent 4xx statuses and deterministic error payloads. Prevent arbitrary or unauthenticated network exposure: default server stays on `127.0.0.1`, CORS restricted to local frontend. No login system is required for local demo.
- Keep feature computations and model loading efficient: avoid repeated reads of all 73,000 sales rows on every individual prediction if cached product history can be fetched; cache immutable saved model artifacts where possible, with invalidation on new version.
- Update or add database migration as necessary, with backup and rollback instructions. Never delete existing user data without explicit permission.

**Exit criteria:** end-to-end create/edit/stock-adjust/simulate/draft/approve/receive/export flows work, with data consistency after refresh/restart.

## Phase 8 — Frontend quality and mockup fidelity (P1)

- Compare existing UI against each image in `mockup-ui/` and preserve the current five-page design direction; refine spacing, responsive behavior, typography, accessible contrast, chart legends, badges, skeletons, loading/errors, and mobile overflow. Maintain the Reorders workflow.
- Ensure every visible chart/KPI/agent field is backed by an API output, or explicitly labeled as demo/illustrative/unavailable. Remove or relabel unsupported “AI confidence,” projected savings, real-time claims and arbitrary live statuses.
- In `Simulator.tsx`, debounce/cancel stale requests and never save or apply a scenario with stale calculation/results; show requested vs normalized quantity and constraints. Improve empty, error and no-model states.
- In `Agents.tsx`, visualize genuine recorded dependency edges and per-agent outputs/latency without claiming synchronous parallel execution if agents run sequentially.
- Add lightweight frontend behavior tests if feasible without substantial dependency bloat; at minimum verify component interactions and browser flows, plus `npm run build`.

**Exit criteria:** all pages render without errors, have sensible responsive behavior, and the primary simulated workflows are manually or automatically verified.

## Phase 9 — MLOps, reproducibility and documentation (P1)

- Ensure artifact metadata includes estimator type, feature schema, training source, train/validation/test periods, seed, evaluation metrics, version, library versions and model integrity checksum where practical. Before loading, validate expected feature schema and library compatibility; load only trusted local artifacts.
- Add lightweight health/diagnostics and saved evaluation runs. Avoid training during API request handling. Document when a full retrain is needed after a new feature schema.
- Create/update simple scripts for setup, bootstrap (non-destructive by default), start API, start UI, verification, and an optional small-sample evaluation. Test the scripts for the current OS. Mention other OS scripts as unverified if not run.
- Add GitHub Actions CI for `pytest` and frontend build **as a file only**; do not push anything. Keep tests fast with small isolated seeded fixtures and no mandatory 200-SKU retraining.
- Update `README.md`, `docs/local-verification.md`, architecture, model-methods, evaluation methodology, tradeoffs, and 4-minute demo script with the **actual** observed results and the precise commands to reproduce them.
- Add a reproducible simple smoke test for local frontend/API connectivity, and optional resource measurements (peak process RSS, disk, training/inference durations) using standard libraries or already-installed tools.

**Exit criteria:** an interviewer can clone the repository, run the documented commands on an 8 GB CPU machine, see consistent honest results, and understand the limitations.

## Required acceptance and evidence

Before declaring completion:

1. Run `python -m pytest -q` (all tests pass), plus newly added leakage/optimizer/pricing/reorder tests.
2. Run `npm run build` with TypeScript checks passing.
3. Run local database/bootstrap/model-status without deleting preexisting work; if bootstrap has already been performed, use a safe temp-data smoke mode or explicitly explain the fallback.
4. Start FastAPI locally, verify `/api/health`, `/api/dashboard`, `/api/products`, `/api/simulate`, `/api/agents`, `/api/performance`, and reorder lifecycle via live HTTP or TestClient. Stop background processes you started.
5. Verify representative frontend flows. If browser automation is available, exercise all six screens; otherwise run frontend tests and provide a clear manual checklist without claiming browser verification.
6. Show examples: price change → revised modeled demand (or clearly supported limitation), reorder qty/lead-time → changed stock trajectories, zero budget → zero purchase, duplicate receive → no extra stock, risk predictions trained with no outcome leakage, honest multi-horizon backtests, nonempty performance chart.
7. Measure/report actual resource footprint if feasible; do not assert that resource targets were met without measurement.
8. Save results in `cursor-prompts/REPAIR_PROGRESS.md`, including every fixed file, commands and outcomes, known unresolved caveats, and any deviations from the plan.
9. Give a compact final report: completed changes grouped by phase, before/after valid metrics, exact local run commands, the remaining limitations and next highest-value optional work.

## Execution rules

- Implement in **small verified increments**: inspect → write a failing regression test → implement the fix → run focused tests → run suite → update progress.
- Read existing code before modifying. Favor minimal safe edits and reuse existing APIs/components. Keep backwards compatibility where reasonable.
- Fix root causes; don't merely hide broken metrics in the UI. Do not game model accuracy or force multi-agent superiority.
- Avoid needless refactors, unrelated features, new dashboards, new LLM agents, AWS deployment, and new infrastructure. The goal is a **correct, polished, fully local StockPilot**.
- If work exceeds the current Cursor context, update `REPAIR_PROGRESS.md` with precise completed stages, failing commands, and next steps so another fresh Cursor chat can resume exactly from the checkpoint.
- If blocked by missing dependencies, permission, or a necessary user decision, identify it precisely, continue with independent tasks, and make no false success claims.

**BEGIN NOW:** inspect the current workspace and git status; record actual baseline checks; create `cursor-prompts/REPAIR_PROGRESS.md`; then start Phase 1 by reproducing the historical backtesting bug with a failing test. Continue through all remaining phases and verify the final local application.
