/** Orchestrator signal-flow. Keep aligned with backend DAG_EDGES in routes.py. */

export type AgentId =
  | "calendar_effect"
  | "price_response"
  | "intermittence"
  | "sales_anomaly"
  | "product_similarity"
  | "demand"
  | "demand_interval"
  | "supplier_eta"
  | "stockout_risk"
  | "excess_risk"
  | "optimizer";

export const ORCH_EDGES: [AgentId, AgentId][] = [
  ["calendar_effect", "demand"],
  ["price_response", "demand"],
  ["intermittence", "demand"],
  ["sales_anomaly", "demand"],
  ["product_similarity", "demand"],
  ["demand", "demand_interval"],
  ["demand", "stockout_risk"],
  ["demand_interval", "stockout_risk"],
  ["supplier_eta", "stockout_risk"],
  ["demand", "excess_risk"],
  ["demand_interval", "excess_risk"],
  ["supplier_eta", "excess_risk"],
  ["demand", "optimizer"],
  ["supplier_eta", "optimizer"],
  ["stockout_risk", "optimizer"],
  ["excess_risk", "optimizer"],
];

export const ORCH_COLUMNS: { title: string; ids: AgentId[] }[] = [
  {
    title: "Business intelligence",
    ids: [
      "calendar_effect",
      "price_response",
      "intermittence",
      "sales_anomaly",
      "product_similarity",
    ],
  },
  { title: "Demand forecasting", ids: ["demand", "demand_interval"] },
  { title: "Supply intelligence", ids: ["supplier_eta"] },
  { title: "Risk prediction", ids: ["stockout_risk", "excess_risk"] },
  { title: "Decision optimization", ids: ["optimizer"] },
];

export const AGENT_COPY: Record<
  AgentId,
  { title: string; purpose: string; inputs: string; outputs: string; algorithm: string }
> = {
  calendar_effect: {
    title: "Calendar effect",
    purpose: "Estimates weekday and event uplift against a mid-week baseline.",
    inputs: "Day-of-week, day-of-month, week, and event features from sales dates",
    outputs: "calendar_uplift (units/day), applied inside the demand model",
    algorithm: "Regression on calendar features",
  },
  price_response: {
    title: "Price response",
    purpose: "Observational association between price, promotions, and units. Not causal elasticity.",
    inputs: "Shelf price, price versus median, promotion flag",
    outputs: "expected_units_delta versus shelf price",
    algorithm: "Regression",
  },
  intermittence: {
    title: "Intermittence",
    purpose: "Detects sparse demand so the forecast can shrink toward zero.",
    inputs: "Recent zero-sale rate features",
    outputs: "p_zero_demand",
    algorithm: "Classifier",
  },
  sales_anomaly: {
    title: "Sales anomaly",
    purpose: "Flags unusual recent sales so demand can blend toward the recent median.",
    inputs: "Demand feature row",
    outputs: "is_anomaly",
    algorithm: "Isolation forest",
  },
  product_similarity: {
    title: "Product similarity",
    purpose: "Borrows a neighbor demand signal when a SKU's own history is thin.",
    inputs: "28-day sales profile",
    outputs: "similarity_demand",
    algorithm: "Nearest-neighbor profiles",
  },
  demand: {
    title: "Demand forecast",
    purpose: "Primary daily demand model. Conditioned by the five upstream signals.",
    inputs: "Lags, rolling stats, calendar, price, and upstream agent outputs",
    outputs: "p50_units and daily_p50",
    algorithm: "Histogram gradient boosting regressor",
  },
  demand_interval: {
    title: "Demand interval",
    purpose: "Builds a nominal p10–p90 (80%) band around the demand point forecast.",
    inputs: "Same features as demand, plus p50",
    outputs: "p10 / p50 / p90 series",
    algorithm: "Quantile gradient boosting",
  },
  supplier_eta: {
    title: "Supplier ETA",
    purpose: "Estimates replenishment lead time from supplier history.",
    inputs: "Supplier delivery history",
    outputs: "eta_days / lead_days",
    algorithm: "Regression",
  },
  stockout_risk: {
    title: "Stockout risk",
    purpose: "Scores shortage risk for a candidate order using decision-time features only.",
    inputs: "Stock, reorder point, pack, demand, p90, lead time, order quantity",
    outputs: "stockout_risk",
    algorithm: "Classifier on simulated supply paths",
  },
  excess_risk: {
    title: "Excess risk",
    purpose: "Scores overstock risk for the same candidate order.",
    inputs: "Decision-time stock, demand, lead time, and order quantity",
    outputs: "excess_risk",
    algorithm: "Classifier on simulated supply paths",
  },
  optimizer: {
    title: "Reorder optimizer",
    purpose: "Chooses a pack-size order quantity from demand, ETA, risks, and budget. Not a trained model.",
    inputs: "Daily demand, lead time, candidate risks, pack size, budget",
    outputs: "suggested_qty",
    algorithm: "Deterministic search over pack multiples",
  },
};

export function dependencyPath(selected: string, edges: [string, string][] = ORCH_EDGES): Set<string> {
  const up = new Set<string>([selected]);
  const down = new Set<string>([selected]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const [from, to] of edges) {
      if (up.has(to) && !up.has(from)) {
        up.add(from);
        grew = true;
      }
      if (down.has(from) && !down.has(to)) {
        down.add(to);
        grew = true;
      }
    }
  }
  return new Set([...up, ...down]);
}

export function edgeOnPath(from: string, to: string, selected: string, edges: [string, string][] = ORCH_EDGES): boolean {
  const up = new Set<string>([selected]);
  const down = new Set<string>([selected]);
  let grew = true;
  while (grew) {
    grew = false;
    for (const [a, b] of edges) {
      if (up.has(b) && !up.has(a)) {
        up.add(a);
        grew = true;
      }
      if (down.has(a) && !down.has(b)) {
        down.add(b);
        grew = true;
      }
    }
  }
  const toward = up.has(from) && up.has(to);
  const away = down.has(from) && down.has(to);
  return toward || away;
}
