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
  inventory_value_paise?: number | null;
  excess_inventory_value_paise?: number | null;
  excess_label?: string | null;
  projected_revenue_trend_pct?: number | null;
  at_risk_delta?: number | null;
  reorders_trend_pct?: number | null;
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
  sell_through?: number | null;
  forecast_28d?: number | null;
}

export interface ProductsListResponse {
  items: ProductRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface InventorySummary {
  total_skus: number;
  low_stock: number;
  overstocked: number;
  avg_days_of_supply: number | null;
  low_stock_rule: string;
  overstock_rule: string;
  categories: string[];
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
  trace_id?: string | null;
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
  provenance?: string;
}

export interface ScenarioDetail extends ScenarioSummary {
  inputs: Partial<SimulateRequest> & Record<string, unknown>;
  results?: Partial<SimulateResponse> | null;
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
    sample_skus?: number | null;
    note?: string;
    rows: {
      strategy: string;
      savings_paise?: number | null;
      cost_paise?: number | null;
      mean_stockout_days?: number | null;
      mean_unmet_demand_units?: number | null;
      note?: string;
    }[];
  };
  expanded_policy_replay?: {
    label?: string;
    sample_skus?: number | null;
    runtime_seconds?: number | null;
    limitation?: string | null;
    rows?: {
      strategy: string;
      cost_paise?: number | null;
      mean_stockout_days?: number | null;
      mean_unmet_demand_units?: number | null;
      mean_purchasing_cash_paise?: number | null;
    }[];
  } | null;
  api_benchmark?: {
    method?: string;
    measured_at?: string;
    endpoints?: { name: string; p50_ms?: number | null; p95_ms?: number | null; max_ms?: number | null; status?: number }[];
  } | null;
  mlops?: { limitations?: string[] } | null;
  agent_latency?: {
    agent_name: string;
    runs: number;
    mean_duration_ms?: number | null;
    max_duration_ms?: number | null;
  }[];
  data_source?: DataSource;
  evaluation_mode?: string;
}

export interface AnalyticsParams {
  date_from?: string;
  date_to?: string;
  year?: string | number;
  month?: string | number;
  category?: string;
  supplier_id?: string | number;
  product_id?: string | number;
  limit?: number;
  cell?: string;
  segment?: string;
  page?: number;
  page_size?: number;
  horizon_days?: number | string;
  mode?: "no_reorder" | "recommended" | "scenario" | string;
  scenario_order_qty?: number;
  scenario_lead_days?: number;
  scenario_product_id?: number;
}

export interface PredictiveFreshness {
  status?: string | null;
  stale_risk_count?: number | null;
  uncovered_count?: number | null;
  label?: string | null;
}

export interface PredictiveForecastCoverage {
  covered?: number;
  selected?: number;
  label?: string;
}

export interface PredictiveKpiMetric<T = number | null> {
  value?: T;
  label?: string;
  definition?: string;
  horizon_days?: number;
  by_horizon?: Record<string, number | null>;
  threshold?: number;
  kind?: string;
  distinct_from?: string;
  policy?: string;
  current_inventory_value_paise?: number | null;
  unavailable_reason?: string | null;
}

export interface PredictiveOverview {
  ready: boolean;
  horizon_days?: number;
  forecast_as_of?: string | null;
  operational_as_of?: string | null;
  model_version?: string | null;
  forecast_source?: string;
  product_count?: number;
  forecast_coverage?: PredictiveForecastCoverage;
  freshness?: PredictiveFreshness;
  interval_note?: string;
  projection_note?: string;
  note?: string | null;
  kpis?: {
    expected_demand_units?: PredictiveKpiMetric;
    products_at_stockout_risk?: PredictiveKpiMetric<number>;
    excess_inventory_value_paise?: PredictiveKpiMetric<number>;
    recommended_replenishment_spend_paise?: PredictiveKpiMetric<number>;
    projected_inventory_value_paise?: PredictiveKpiMetric<number>;
    forecast_coverage?: PredictiveForecastCoverage;
  };
  live_stock_units?: number | null;
  live_inventory_value_paise?: number | null;
  provenance?: string;
}

export interface PredictiveDemandPoint {
  date: string;
  actual_units?: number | null;
  p10?: number | null;
  p50?: number | null;
  p90?: number | null;
  is_forecast?: boolean;
  sku_count?: number;
  interval_kind?: string;
}

export interface PredictiveDemand {
  ready: boolean;
  forecast_as_of?: string | null;
  horizon_days?: number;
  model_version?: string | null;
  forecast_coverage?: PredictiveForecastCoverage;
  freshness?: PredictiveFreshness;
  history?: PredictiveDemandPoint[];
  forecast?: PredictiveDemandPoint[];
  series?: PredictiveDemandPoint[];
  interval_note?: string;
  aggregation?: string;
  note?: string | null;
}

export interface PredictiveProjectionPoint {
  date: string;
  is_forecast?: boolean;
  projected_inventory_units?: number;
  projected_inventory_value_paise?: number;
  predicted_demand?: number;
  fulfilled_units?: number;
  receipts?: number;
  unmet_demand?: number;
  scenario?: string;
  forecast_as_of?: string;
}

export interface PredictiveProjection {
  ready: boolean;
  forecast_as_of?: string | null;
  mode?: string;
  horizon_days?: number;
  model_version?: string | null;
  forecast_coverage?: PredictiveForecastCoverage;
  freshness?: PredictiveFreshness;
  history?: {
    date: string;
    inventory_value_paise?: number;
    projected_inventory_value_paise?: number;
    projected_inventory_units?: number;
    stock_units?: number;
    is_forecast?: boolean;
  }[];
  series?: PredictiveProjectionPoint[];
  opening_inventory_value_paise?: number | null;
  ending_inventory_value_paise?: number | null;
  projection_note?: string;
  notes?: string[];
  note?: string | null;
}

export interface PredictiveRiskProduct {
  product_id: number;
  sku: string;
  name: string;
  category?: string;
  current_stock: number;
  stock_value_paise: number;
  forecast_demand_28d?: number | null;
  stockout_risk?: number | null;
  risk_band?: string;
  days_of_supply?: number | null;
  risk_freshness?: string;
  suggested_qty?: number | null;
  estimated_cost_paise?: number | null;
  expected_arrival_date?: string | null;
  trace_id?: string | null;
  excess_risk?: number | null;
}

export interface PredictiveRisks {
  ready: boolean;
  forecast_as_of?: string | null;
  model_version?: string | null;
  freshness?: PredictiveFreshness;
  thresholds?: { high?: number; moderate?: number; definition?: string };
  distribution?: Record<string, number>;
  at_risk_count?: number;
  operational_high_risk_level_count?: number;
  categories?: { category: string; at_risk_skus: number; sku_count: number; stock_value_paise: number; avg_days_of_supply?: number | null }[];
  products?: PredictiveRiskProduct[];
  excess?: {
    items?: PredictiveExcessItem[];
    proxy_definition?: string;
    modeled_risk_definition?: string;
  };
  aggregation_note?: string;
  note?: string | null;
}

export interface PredictiveExcessItem {
  product_id: number;
  sku: string;
  name: string;
  category?: string;
  current_stock: number;
  excess_units_proxy: number;
  excess_value_paise_proxy: number;
  days_of_supply?: number | null;
  modeled_excess_risk?: number | null;
  forecast_28d?: number | null;
}

export interface PredictiveRecommendationItem {
  product_id: number;
  sku: string;
  name: string;
  category?: string;
  current_stock: number;
  pack_size?: number;
  suggested_qty: number;
  estimated_cost_paise: number;
  forecast_demand_28d?: number | null;
  stockout_risk?: number | null;
  excess_risk?: number | null;
  expected_arrival_date?: string | null;
  arrival_date_role?: string;
  days_of_supply?: number | null;
  status?: string;
  trace_id?: string | null;
  constraints?: string[];
  explanation?: string;
}

export interface PredictiveRecommendations {
  ready: boolean;
  forecast_as_of?: string | null;
  model_version?: string | null;
  total_recommended_spend_paise?: number;
  ranking_rule?: string;
  items: PredictiveRecommendationItem[];
  insights?: { id: string; title?: string; severity?: string; text: string }[];
  note?: string | null;
}

export interface PredictiveExplain {
  ready: boolean;
  product: {
    product_id: number;
    sku: string;
    name: string;
    category?: string;
    stock_on_hand: number;
    unit_cost_paise?: number;
    pack_size?: number;
    stockout_risk?: number | null;
    days_of_supply?: number | null;
    risk_freshness?: string;
  };
  forecast_as_of?: string | null;
  model_version?: string | null;
  forecast_demand_28d?: number | null;
  recommendation?: {
    suggested_qty?: number;
    estimated_cost_paise?: number | null;
    expected_arrival_date?: string | null;
    expected_stockout_risk?: number | null;
    expected_excess_risk?: number | null;
    trace_id?: string | null;
    explanation?: string;
    constraints?: string[];
  } | null;
  comparison?: {
    no_reorder?: { ending_inventory_value_paise?: number; total_unmet_demand_units?: number; series?: PredictiveProjectionPoint[] };
    recommended?: { ending_inventory_value_paise?: number; total_unmet_demand_units?: number; series?: PredictiveProjectionPoint[] };
    label?: string;
  };
  links?: { simulator?: string; agents?: string; inventory?: string; performance?: string };
  note?: string | null;
}

export interface PredictiveDataQuality {
  ready: boolean;
  forecast?: Record<string, unknown>;
  forecast_coverage?: PredictiveForecastCoverage;
  freshness?: PredictiveFreshness;
  model_versions?: { agent_name: string; version?: string; trained_at?: string; training_source?: string }[];
  historical_analytics?: Record<string, unknown>;
  stale_risk_count?: number;
  limitations?: string[];
  interval_note?: string;
  projection_note?: string;
}

export interface AnalyticsInsight {
  id: string;
  text: string;
}

export interface AnalyticsMonth {
  month: string;
  inventory_value_paise?: number | null;
  stock_units?: number | null;
  revenue_paise?: number | null;
  cogs_paise?: number | null;
  average_inventory_value_paise?: number | null;
  turnover?: number | null;
  inventory_to_sales?: number | null;
  days?: number;
  absolute_change_paise?: number | null;
  percent_change?: number | null;
  previous_inventory_value_paise?: number | null;
}

export interface AnalyticsOverview {
  ready: boolean;
  provenance?: string;
  run_id?: number | null;
  seed?: number | null;
  snapshot_date?: string | null;
  generated_at?: string | null;
  note?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  period_days?: number | null;
  inventory_value_paise?: number | null;
  stock_units?: number | null;
  live_inventory_value_paise?: number | null;
  live_stock_units?: number | null;
  live_matches_period_end?: boolean | null;
  turnover?: number | null;
  turnover_definition?: string;
  turnover_reference_target?: number | null;
  days_inventory_outstanding?: number | null;
  dio_definition?: string;
  inventory_to_sales?: number | null;
  inventory_to_sales_definition?: string;
  cogs_paise?: number | null;
  revenue_paise?: number | null;
  excess_inventory_value_paise?: number | null;
  excess_definition?: string;
  cost_model?: string;
  reconciliation_note?: string | null;
  insights?: AnalyticsInsight[];
  freshness?: string | null;
  source_fingerprint?: string | null;
  algorithm_version?: string | null;
  anchor_note?: string | null;
  historical_label?: string | null;
  current_label?: string | null;
  stock_units_meaning?: string | null;
  live_stock_meaning?: string | null;
  excess_meaning?: string | null;
  reconciliation?: ReconciliationSummary | null;
}

export interface ReconciliationSummary {
  products_up?: number | null;
  products_down?: number | null;
  products_matched?: number | null;
  up_units?: number | null;
  down_units?: number | null;
  up_value_paise?: number | null;
  down_value_paise?: number | null;
  net_value_paise?: number | null;
  absolute_value_paise?: number | null;
  reconciliation_date?: string | null;
  in_selected_window?: boolean | null;
  provenance?: string | null;
  explanation?: string | null;
}

export interface RankedProduct {
  rank: number;
  product_id: number;
  sku: string;
  name: string;
  category?: string;
  inventory_value_paise: number;
  stock_units: number;
  revenue_paise: number;
  sold_units: number;
}

export interface MovementReport {
  ready: boolean;
  note?: string | null;
  formula?: string;
  conserved_units?: boolean | null;
  conserved_value?: boolean | null;
  opening_units?: number | null;
  receipts_units?: number | null;
  fulfilled_sales_units?: number | null;
  returns_units?: number | null;
  adjustments_units?: number | null;
  writeoff_units?: number | null;
  routine_receipts_units?: number | null;
  reconciliation_receipt_units?: number | null;
  routine_writeoff_units?: number | null;
  reconciliation_writeoff_units?: number | null;
  closing_units?: number | null;
  opening_value_paise?: number | null;
  receipts_value_paise?: number | null;
  cogs_paise?: number | null;
  returns_value_paise?: number | null;
  adjustments_value_paise?: number | null;
  writeoff_value_paise?: number | null;
  closing_value_paise?: number | null;
}

export interface AbcCell {
  cell: string;
  abc: string;
  xyz: string;
  sku_count: number;
  inventory_value_paise: number;
  revenue_paise: number;
  value_share?: number | null;
  interpretation: string;
}

export interface AbcProduct {
  product_id: number;
  sku: string;
  name: string;
  category?: string;
  cell: string;
  abc: string;
  xyz: string;
  revenue_paise: number;
  inventory_value_paise: number;
  cv?: number | null;
  interpretation: string;
}

export interface SlowItem {
  product_id: number;
  sku: string;
  name: string;
  category?: string;
  stock_units: number;
  inventory_value_paise: number;
  historical_stock_units?: number | null;
  current_stock_units?: number | null;
  sales_time_basis?: string | null;
  forecast_time_basis?: string | null;
  sold_units_30d: number;
  sold_units_90d: number;
  forecast_daily_demand?: number | null;
  forecast_days_of_supply?: number | null;
  days_since_recorded_sale?: number | null;
  excess_units?: number | null;
  excess_value_paise?: number | null;
  risk_level?: string | null;
  suggested_action: string;
  action_basis: string;
}

export interface SupplierScore {
  supplier_id: number;
  name: string;
  product_count: number;
  stock_units: number;
  stock_value_paise: number;
  modeled_lead_days: number;
  catalog_reliability: number;
  simulated_receipts: number;
  simulated_on_time_rate?: number | null;
  average_delay_days?: number | null;
  open_reorder_qty: number;
}

export interface AnalyticsFilters {
  ready: boolean;
  note?: string | null;
  categories: string[];
  suppliers: { id: number; name: string }[];
  products: { id: number; sku: string; name: string; category?: string }[];
  years: number[];
  months: string[];
  date_min?: string | null;
  date_max?: string | null;
}

export interface CalendarItem {
  id: string;
  kind: string;
  product_id?: number | null;
  title: string;
  status?: string | null;
  qty?: number | null;
  trace_id?: string | null;
  date?: string | null;
  date_role: "actual" | "predicted" | "unavailable" | string;
  detail: string;
  limitation?: string | null;
}

export interface ApiErrorBody {
  detail?: string | { msg: string }[];
  message?: string;
}

/** REAL_RETAIL_UCI evaluation track (isolated from SYNTHETIC_DEMO). */
export interface RealDataStatus {
  experiment_id: string;
  raw_xlsx_present: boolean;
  daily_sales_present: boolean;
  splits_present: boolean;
  models_present: boolean;
  metrics_present: boolean;
  ready_for_ui: boolean;
  metrics_summary?: {
    wape?: number | null;
    mae?: number | null;
    rmse?: number | null;
    best_wape_method?: string | null;
    evaluation_mode?: string | null;
    model_version?: string | null;
  } | null;
  selected_sku_count?: number | null;
  split_ranges?: Record<string, string> | null;
  reports_dir?: string;
  models_dir?: string;
}

export interface RealDataSummary {
  experiment_id: string;
  dataset_name: string;
  attribution: string;
  source_url: string;
  doi: string;
  license: string;
  currency: string;
  ready: boolean;
  status: RealDataStatus;
  metrics?: RealDataMetrics | null;
  data_quality?: {
    before?: Record<string, unknown> | null;
    after?: Record<string, unknown> | null;
  } | null;
  split_summary?: {
    boundaries?: Record<string, string>;
    sku_selection?: { n_selected?: number; selected_stock_codes?: string[]; criteria?: string };
    train?: { rows?: number; zero_sale_rate?: number };
    validation?: { rows?: number };
    test?: { rows?: number; zero_sale_rate?: number };
  } | null;
  limitations?: string[];
}

export interface RealDataMetrics {
  experiment_id?: string;
  model_version?: string;
  evaluation_mode?: string;
  n_test_rows?: number;
  n_skus?: number;
  currency?: string;
  ml?: { mae?: number | null; rmse?: number | null; wape?: number | null };
  baselines?: {
    seasonal_naive_7?: { mae?: number | null; rmse?: number | null; wape?: number | null };
    moving_average_28?: { mae?: number | null; rmse?: number | null; wape?: number | null };
  };
  interval?: {
    pinball_p10?: number | null;
    pinball_p90?: number | null;
    empirical_coverage_p10_p90?: number | null;
    mean_interval_width?: number | null;
    nominal_label?: string;
  };
  intermittence?: {
    brier?: number | null;
    precision?: number | null;
    recall?: number | null;
    f1?: number | null;
    roc_auc?: number | null;
    target_label?: string;
  };
  best_wape_method?: string | null;
  notes?: string[];
  segments?: Record<string, unknown>;
}

export interface RealDataBaselineRow {
  method: string;
  mae?: number | null;
  rmse?: number | null;
  wape?: number | null;
}

export interface RealDataPredictionRow {
  date: string;
  stock_code: string;
  product_id?: number;
  actual_units: number;
  predicted_units: number;
  seasonal_naive_units?: number;
  moving_average_units?: number;
  p10_units?: number;
  p50_units?: number;
  p90_units?: number;
  abs_error?: number;
  model_version?: string;
  dataset_source?: string;
  evaluation_mode?: string;
}

export interface RealDataMetadata {
  experiment_id: string;
  dataset_name: string;
  source_url: string;
  doi: string;
  license: string;
  attribution: string;
  currency: string;
  raw_columns?: string[];
  daily_sales_columns?: string[];
  provenance_label?: string;
  synthetic_label?: string;
  cleaning_counts?: Record<string, unknown> | null;
  sample_paths?: Record<string, string>;
  training?: {
    model_version?: string;
    trained_at?: string;
    feature_columns?: string[];
    seed?: number;
  };
  manifest?: Record<string, unknown>;
}
