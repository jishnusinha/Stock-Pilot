export type DataSource = string;

export interface HealthResponse {
  status: string;
  db_ready: boolean;
  models_available: number;
  models_expected: number;
  demo_date?: string;
  version?: string;
}

export interface DashboardKpis {
  projected_revenue_paise?: number | null;
  at_risk_products?: number | null;
  suggested_reorders?: number | null;
  estimated_savings_paise?: number | null;
  savings_label?: string;
  projected_revenue_trend_pct?: number | null;
  at_risk_delta?: number | null;
  reorders_trend_pct?: number | null;
  savings_trend_pct?: number | null;
}

export interface ForecastPoint {
  date: string;
  actual?: number | null;
  p50?: number | null;
  p10?: number | null;
  p90?: number | null;
  is_forecast?: boolean;
}

export interface DashboardAlert {
  id: string;
  severity: "critical" | "warning" | "info";
  title: string;
  message: string;
  product_id?: number | null;
}

export interface RiskSkuRow {
  product_id: number;
  sku: string;
  name: string;
  category?: string;
  current_stock: number;
  days_of_supply?: number | null;
  forecast_4wk_units?: number | null;
  risk_level: "high" | "medium" | "low";
}

export interface DashboardRecommendation {
  id?: number | null;
  product_id: number;
  title: string;
  message: string;
  suggested_qty?: number | null;
  impact_label?: string;
}

export interface DashboardResponse {
  kpis: DashboardKpis;
  forecast_series: ForecastPoint[];
  alerts: DashboardAlert[];
  top_risk: RiskSkuRow[];
  recommendation?: DashboardRecommendation | null;
  data_source?: DataSource;
  as_of?: string;
}

export interface ProductRow {
  id: number;
  sku: string;
  name: string;
  category?: string;
  supplier_name?: string;
  supplier_id?: number;
  current_stock: number;
  days_of_supply?: number | null;
  risk_level?: "high" | "medium" | "low" | string;
  unit_price_paise?: number;
  unit_cost_paise?: number;
  reorder_point?: number;
  pack_size?: number;
}

export interface ProductsListResponse {
  items: ProductRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProductDetail {
  id: number;
  sku: string;
  name: string;
  category?: string;
  description?: string;
  current_stock: number;
  unit_price_paise?: number;
  unit_cost_paise?: number;
  pack_size?: number;
  supplier?: Supplier;
  risk_level?: string;
  days_of_supply?: number | null;
  forecast?: ForecastPoint[];
  sales_history?: { date: string; units: number }[];
  movements?: StockMovement[];
  reorder_recommendation?: ReorderRecommendation | null;
  data_source?: DataSource;
}

export interface Supplier {
  id: number;
  name: string;
  lead_time_days?: number;
  reliability_score?: number | null;
}

export interface StockMovement {
  id: number;
  created_at: string;
  delta: number;
  reason: string;
  balance_after?: number;
}

export interface ReorderRecommendation {
  id?: number;
  suggested_qty?: number;
  rationale?: string;
  product_id?: number;
}

export interface AdjustStockRequest {
  delta: number;
  reason: string;
}

export interface ProductCreateRequest {
  sku: string;
  name: string;
  category: string;
  supplier_id: number;
  unit_cost_paise: number;
  selling_price_paise: number;
  stock_on_hand?: number;
  reorder_point?: number;
  pack_size?: number;
  shelf_life_days?: number | null;
}

export interface ProductUpdateRequest {
  name?: string;
  category?: string;
  supplier_id?: number;
  unit_cost_paise?: number;
  selling_price_paise?: number;
  reorder_point?: number;
  pack_size?: number;
  shelf_life_days?: number | null;
}

export interface SimulateRequest {
  product_id: number;
  reorder_qty: number;
  proposed_price_paise: number;
  lead_time_days: number;
  budget_paise: number;
  horizon_days?: number;
}

export interface SimulateMetrics {
  stockout_days?: number | null;
  unmet_demand_units?: number | null;
  stockout_probability?: number | null;
  excess_risk_units?: number | null;
  purchase_cost_paise?: number | null;
  revenue_paise?: number | null;
  gross_margin_paise?: number | null;
}

export interface SimulateSeriesPoint {
  date: string;
  inventory: number;
}

export interface SimulateResponse {
  baseline_label: string;
  proposed_label: string;
  baseline_series: SimulateSeriesPoint[];
  proposed_series: SimulateSeriesPoint[];
  baseline_metrics: SimulateMetrics;
  proposed_metrics: SimulateMetrics;
  comparison_rows?: SimulateComparisonRow[];
  arrival_date?: string;
  data_source?: DataSource;
  requested_qty?: number;
  applied_qty?: number;
  qty_normalization_note?: string;
  price_effect?: {
    type?: string;
    units_delta?: number;
    not_causal_elasticity?: boolean;
    baseline_price_paise?: number;
    proposed_price_paise?: number;
  };
  explanation?: string;
}

export interface SimulateComparisonRow {
  metric: string;
  baseline: string | number;
  proposed: string | number;
  delta?: string;
}

export interface SaveScenarioRequest {
  name: string;
  product_id: number;
  inputs: SimulateRequest;
  results?: Partial<SimulateResponse>;
}

export interface ScenarioSummary {
  id: number;
  name: string;
  product_id: number;
  created_at: string;
}

export interface ReorderCreateRequest {
  product_id: number;
  qty: number;
  notes?: string;
  recommendation_id?: number;
}

export interface ReorderRow {
  id: number;
  product_id: number;
  sku?: string;
  product_name?: string;
  qty: number;
  status: "pending" | "approved" | "rejected" | "received" | string;
  created_at: string;
  unit_cost_paise?: number;
  total_paise?: number;
}

export interface AgentCard {
  id: string;
  name: string;
  method?: string;
  data_source?: string;
  status: "active" | "ready" | "unavailable" | string;
  artifact_available: boolean;
  latency_median_ms?: number | null;
  latency_p95_ms?: number | null;
  last_run_at?: string | null;
  key_output?: string;
  confidence?: number | null;
}

export interface AgentRunSummary {
  trace_id: string;
  scenario?: string;
  agents: string[];
  status: string;
  started_at: string;
  duration_ms?: number;
  recommendation?: string;
}

export interface AgentRunTrace {
  trace_id: string;
  nodes: AgentTraceNode[];
  edges?: { from: string; to: string }[];
  status: string;
  total_duration_ms?: number;
}

export interface AgentTraceNode {
  agent_id: string;
  name: string;
  status: string;
  duration_ms?: number;
  output_summary?: string;
}

export interface PerformanceMetric {
  id: string;
  label: string;
  value: number | string | null;
  unit?: string;
  measured: boolean;
  tooltip?: string;
  source?: string;
}

export interface ModelVersion {
  name: string;
  version?: string;
  trained_at?: string | null;
  status: string;
  source?: string;
}

export interface PerformanceResponse {
  kpis: PerformanceMetric[];
  backtest_series?: { date: string; actual: number; predicted: number }[];
  baseline_comparison?: {
    name: string;
    wape?: number | null;
    mae?: number | null;
  }[];
  coverage?: {
    nominal: string;
    empirical?: number | null;
    pinball_loss?: number | null;
  };
  model_versions: ModelVersion[];
  business_simulation?: {
    label: string;
    rows: {
      strategy: string;
      savings_paise?: number | null;
      cost_paise?: number | null;
      mean_stockout_days?: number | null;
      mean_unmet_demand_units?: number | null;
      note?: string;
    }[];
  };
  data_source?: DataSource;
  evaluation_mode?: string;
}

export interface ApiErrorBody {
  detail?: string | { msg: string }[];
  message?: string;
}
