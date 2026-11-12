# Product contract

## What StockPilot is
Local-first B2B inventory intelligence demo for one synthetic retailer. **No LLM / chatbot.** Predictions come from ten fitted traditional ML models (scikit-learn) plus a deterministic reorder optimizer.

## Provenance rules
- Demo dataset labeled `SYNTHETIC_DEMO`.
- Supplier lead-time / stockout / excess labels from `SIMULATED_SUPPLY` trajectories.
- UI must show `Demo data · Simulated supplier/stock outcomes` where relevant.
- Never invent confidence percentages; if unmeasured show `Not measured` / `N/A`.
- Nominal demand intervals are **p10–p90 (80% coverage)**, not “95% confidence” unless a true 95% interval is computed.
- Business savings from inventory replay are **simulation-derived** and labeled as such.

## Money & dates
- Store money as integer **paise**; display as ₹.
- Demo snapshot date default `2026-11-01` (`STOCKPILOT_DEMO_DATE`).
- Show `Demo snapshot as of …` rather than implying live calendar claims.

## Routes
| Route | Purpose |
|---|---|
| `/` | Command Center |
| `/inventory` | Inventory Explorer |
| `/simulator` | What-If Simulator |
| `/agents` | Agent Intelligence |
| `/performance` | Model Performance |
| `/reorders` | Reorder workflow |

## Explicit exclusions
No payments, real supplier APIs, multi-tenant auth, email, cloud deploy, mobile native apps, live POS, Kaggle/M5 requirement, conversational AI answers, or automated external ordering.

## No-LLM statement
All natural-language recommendations are **template strings** filled from structured model/optimizer outputs. There is no generative language model in the stack.
