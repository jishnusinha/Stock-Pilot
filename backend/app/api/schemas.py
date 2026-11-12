"""Pydantic request/response models aligned with frontend types."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    db_ready: bool
    models_available: int
    models_expected: int = 10
    demo_date: str | None = None
    version: str | None = None
    demo_mode: bool = True


class DashboardKpis(BaseModel):
    projected_revenue_paise: int | None = None
    at_risk_products: int | None = None
    suggested_reorders: int | None = None
    estimated_savings_paise: int | None = None
    savings_label: str | None = "Simulation estimate"
    projected_revenue_trend_pct: float | None = None
    at_risk_delta: int | None = None
    reorders_trend_pct: float | None = None
    savings_trend_pct: float | None = None


class ForecastPoint(BaseModel):
    date: str
    actual: float | None = None
    p50: float | None = None
    p10: float | None = None
    p90: float | None = None
    is_forecast: bool = False


class DashboardAlert(BaseModel):
    id: str
    severity: Literal["critical", "warning", "info"]
    title: str
    message: str
    product_id: int | None = None


class RiskSkuRow(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str | None = None
    current_stock: int
    days_of_supply: float | None = None
    forecast_4wk_units: float | None = None
    risk_level: str


class DashboardRecommendation(BaseModel):
    id: int | None = None
    product_id: int
    title: str
    message: str
    suggested_qty: int | None = None
    impact_label: str | None = "ML recommendation"


class DashboardResponse(BaseModel):
    kpis: DashboardKpis
    forecast_series: list[ForecastPoint]
    alerts: list[DashboardAlert]
    top_risk: list[RiskSkuRow]
    recommendation: DashboardRecommendation | None = None
    data_source: str = "SYNTHETIC_DEMO"
    as_of: str | None = None


class ProductRow(BaseModel):
    id: int
    sku: str
    name: str
    category: str | None = None
    supplier_name: str | None = None
    supplier_id: int | None = None
    current_stock: int
    days_of_supply: float | None = None
    risk_level: str | None = None
    unit_price_paise: int | None = None
    unit_cost_paise: int | None = None
    reorder_point: int | None = None
    pack_size: int | None = None
    sell_through: float | None = None
    forecast_28d: float | None = None


class ProductsListResponse(BaseModel):
    items: list[ProductRow]
    total: int
    page: int
    page_size: int


class Supplier(BaseModel):
    id: int
    name: str
    lead_time_days: int | None = None
    reliability_score: float | None = None


class StockMovement(BaseModel):
    id: int
    created_at: str
    delta: int
    reason: str
    balance_after: int | None = None


class ReorderRecommendation(BaseModel):
    id: int | None = None
    suggested_qty: int | None = None
    rationale: str | None = None
    product_id: int | None = None


class ProductDetail(BaseModel):
    id: int
    sku: str
    name: str
    category: str | None = None
    description: str | None = None
    current_stock: int
    unit_price_paise: int | None = None
    unit_cost_paise: int | None = None
    pack_size: int | None = None
    supplier: Supplier | None = None
    risk_level: str | None = None
    days_of_supply: float | None = None
    forecast: list[ForecastPoint] = Field(default_factory=list)
    sales_history: list[dict[str, Any]] = Field(default_factory=list)
    movements: list[StockMovement] = Field(default_factory=list)
    reorder_recommendation: ReorderRecommendation | None = None
    data_source: str = "SYNTHETIC_DEMO"


class AdjustStockRequest(BaseModel):
    delta: int
    reason: str = "manual_adjustment"


class ProductCreateRequest(BaseModel):
    sku: str
    name: str
    category: str = "General"
    supplier_id: int
    unit_cost_paise: int
    selling_price_paise: int
    stock_on_hand: int = 0
    reorder_point: int | None = None
    pack_size: int = 12
    shelf_life_days: int | None = None


class ProductUpdateRequest(BaseModel):
    name: str | None = None
    category: str | None = None
    supplier_id: int | None = None
    unit_cost_paise: int | None = None
    selling_price_paise: int | None = None
    reorder_point: int | None = None
    pack_size: int | None = None
    shelf_life_days: int | None = None


class SimulateRequest(BaseModel):
    product_id: int
    reorder_qty: int = Field(ge=0)
    proposed_price_paise: int = Field(gt=0)
    lead_time_days: int = Field(ge=0, le=60)
    budget_paise: int = Field(ge=0)
    horizon_days: int = Field(default=28, ge=7, le=90)


class SimulateMetrics(BaseModel):
    stockout_days: int | None = None
    unmet_demand_units: float | None = None
    stockout_probability: float | None = None
    excess_risk_units: float | None = None
    purchase_cost_paise: int | None = None
    revenue_paise: int | None = None
    gross_margin_paise: int | None = None


class SimulateSeriesPoint(BaseModel):
    date: str
    inventory: int


class SimulateComparisonRow(BaseModel):
    metric: str
    baseline: str | float | int
    proposed: str | float | int
    delta: str | None = None


class SimulateResponse(BaseModel):
    baseline_label: str = "Current plan"
    proposed_label: str = "Proposed plan"
    baseline_series: list[SimulateSeriesPoint]
    proposed_series: list[SimulateSeriesPoint]
    baseline_metrics: SimulateMetrics
    proposed_metrics: SimulateMetrics
    comparison_rows: list[SimulateComparisonRow] = Field(default_factory=list)
    arrival_date: str | None = None
    data_source: str = "SIMULATED_SUPPLY"
    recommendation_id: int | None = None
    explanation: str | None = None


class SaveScenarioRequest(BaseModel):
    name: str
    product_id: int
    inputs: dict[str, Any]
    results: dict[str, Any] | None = None


class ScenarioSummary(BaseModel):
    id: int
    name: str | None = None
    product_id: int
    created_at: str
    provenance: str | None = None


class ReorderCreateRequest(BaseModel):
    product_id: int
    qty: int = Field(ge=1)
    notes: str | None = None
    recommendation_id: int | None = None


class ReorderRow(BaseModel):
    id: int
    product_id: int
    sku: str | None = None
    product_name: str | None = None
    qty: int
    status: str
    created_at: str
    unit_cost_paise: int | None = None
    total_paise: int | None = None


class AgentCard(BaseModel):
    id: str
    name: str
    method: str | None = None
    data_source: str | None = None
    status: str
    artifact_available: bool
    latency_median_ms: float | None = None
    latency_p95_ms: float | None = None
    last_run_at: str | None = None
    key_output: str | None = None
    confidence: float | None = None


class AgentRunSummary(BaseModel):
    trace_id: str
    scenario: str | None = None
    agents: list[str] = Field(default_factory=list)
    status: str
    started_at: str
    duration_ms: float | None = None
    recommendation: str | None = None


class AgentTraceNode(BaseModel):
    agent_id: str
    name: str
    status: str
    duration_ms: float | None = None
    output_summary: str | None = None


class AgentRunTrace(BaseModel):
    trace_id: str
    nodes: list[AgentTraceNode]
    edges: list[dict[str, str]] = Field(default_factory=list)
    status: str
    total_duration_ms: float | None = None


class TriggerRunRequest(BaseModel):
    product_id: int


class PerformanceMetric(BaseModel):
    id: str
    label: str
    value: float | str | None
    unit: str | None = None
    measured: bool
    tooltip: str | None = None
    source: str | None = None


class ModelVersionOut(BaseModel):
    name: str
    version: str | None = None
    trained_at: str | None = None
    status: str
    source: str | None = None


class PerformanceResponse(BaseModel):
    kpis: list[PerformanceMetric]
    backtest_series: list[dict[str, Any]] = Field(default_factory=list)
    baseline_comparison: list[dict[str, Any]] = Field(default_factory=list)
    coverage: dict[str, Any] | None = None
    model_versions: list[ModelVersionOut]
    business_simulation: dict[str, Any] | None = None
    data_source: str = "SYNTHETIC_DEMO"
