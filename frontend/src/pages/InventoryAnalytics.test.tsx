import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InventoryAnalytics } from "./InventoryAnalytics";

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", ResizeObserverStub);

const predictiveOverviewMock = {
  ready: true,
  forecast_as_of: "2026-11-01",
  operational_as_of: "2026-11-13",
  model_version: "1.0.0",
  horizon_days: 28,
  freshness: { status: "current", stale_risk_count: 2 },
  kpis: {
    expected_demand_units: { value: 420, label: "Expected demand · Next 28 days", by_horizon: { "7": 100, "14": 210, "28": 420 } },
    products_at_stockout_risk: { value: 3, definition: "Count of SKUs with modeled stockout_risk ≥ 70% (not a summed probability)." },
    excess_inventory_value_paise: { value: 15000, definition: "Proxy cover" },
    recommended_replenishment_spend_paise: { value: 48000, definition: "Open recommendations" },
    projected_inventory_value_paise: { value: 250000, current_inventory_value_paise: 240000, policy: "no_reorder" },
    forecast_coverage: { covered: 6, selected: 6, label: "6 / 6 SKUs covered" },
  },
};

vi.mock("../api/client", () => ({
  api: {
    analyticsOverview: (params?: { segment?: string }) => Promise.resolve({
      ready: true,
      period_start: "2026-01-01",
      period_end: "2026-02-28",
      period_days: 59,
      inventory_value_paise: params?.segment === "AX" ? 424200 : 250000,
      stock_units: params?.segment === "AX" ? 4 : 40,
      live_inventory_value_paise: 250000,
      live_stock_units: 40,
      turnover: 2.5,
      turnover_reference_target: 6,
      inventory_to_sales: 0.4,
      days_inventory_outstanding: 23.6,
      excess_inventory_value_paise: 10000,
      freshness: "fresh",
      source_fingerprint: "abc123def4567890",
      algorithm_version: "v1",
      run_id: 1,
      reconciliation: {
        products_up: 2,
        products_down: 1,
        products_matched: 0,
        up_value_paise: 3000,
        down_value_paise: 800,
        absolute_value_paise: 3800,
        explanation: "Terminal reconciliation aligns the final day to the frozen stock anchor.",
      },
      insights: [{ id: "top", text: "Dairy Item 1 holds the largest period-end inventory value." }],
      cost_model: "Fixed catalog unit cost.",
      reconciliation_note: "Snapshots are immutable.",
    }),
    analyticsTrend: () => Promise.resolve({
      ready: true,
      months: [{ month: "2026-01", inventory_value_paise: 200000, previous_inventory_value_paise: null, absolute_change_paise: null, percent_change: null, revenue_paise: 80000, inventory_to_sales: 2.5 }],
    }),
    analyticsTurnover: () => Promise.resolve({ ready: true, months: [{ month: "2026-01", turnover: 1.2, cogs_paise: 50000, average_inventory_value_paise: 40000 }], definition: "Month COGS / average inventory." }),
    analyticsMovements: () => Promise.resolve({
      ready: true,
      formula: "closing = opening + receipts + returns + adjustments - fulfilled sales - write-offs",
      conserved_units: true,
      conserved_value: true,
      opening_units: 10,
      receipts_units: 8,
      fulfilled_sales_units: 5,
      returns_units: 1,
      adjustments_units: 0,
      writeoff_units: 0,
      closing_units: 14,
      closing_value_paise: 14000,
    }),
    analyticsTop: () => Promise.resolve({
      ready: true,
      by_value: [{ rank: 1, product_id: 7, sku: "SKU-0007", name: "Value Leader", category: "Dairy", inventory_value_paise: 90000, stock_units: 4, revenue_paise: 1000, sold_units: 2 }],
      by_quantity: [{ rank: 1, product_id: 8, sku: "SKU-0008", name: "Quantity Leader", category: "Snacks", inventory_value_paise: 1000, stock_units: 80, revenue_paise: 500, sold_units: 9 }],
    }),
    analyticsSales: () => Promise.resolve({ ready: true, months: [{ month: "2026-01", inventory_value_paise: 200000, revenue_paise: 80000, inventory_to_sales: 2.5 }] }),
    analyticsCategories: () => Promise.resolve({ ready: true, categories: [{ category: "Dairy", sku_count: 2, inventory_value_paise: 90000, revenue_paise: 1000, value_share: 0.8 }] }),
    analyticsAbc: () => Promise.resolve({
      ready: true,
      abc_rule: "A is the top 80 percent.",
      xyz_rule: "X is stable demand.",
      cells: [{ cell: "AX", abc: "A", xyz: "X", sku_count: 1, inventory_value_paise: 90000, revenue_paise: 1000, value_share: 1, interpretation: "High revenue contribution and relatively stable demand." }],
      products: [{ product_id: 7, sku: "SKU-0007", name: "Value Leader", cell: "AX", abc: "A", xyz: "X", revenue_paise: 1000, inventory_value_paise: 90000, interpretation: "High revenue contribution and relatively stable demand." }],
      total: 1,
    }),
    analyticsSlow: () => Promise.resolve({ ready: true, definition: "No expiry dates are shown.", items: [], total: 0 }),
    analyticsSuppliers: () => Promise.resolve({
      ready: true,
      catalog_reliability_label: "Catalog parameter, not a measured on-time rate.",
      simulated_label: "Simulated from reconstructed receipts.",
      items: [{ supplier_id: 1, name: "Northwind Foods", product_count: 2, stock_units: 10, stock_value_paise: 5000, modeled_lead_days: 5, catalog_reliability: 0.9, simulated_receipts: 3, simulated_on_time_rate: 0.67, average_delay_days: 0.4, open_reorder_qty: 0 }],
    }),
    analyticsFilters: () => Promise.resolve({ ready: true, categories: ["Dairy"], suppliers: [{ id: 1, name: "Northwind Foods" }], products: [{ id: 7, sku: "SKU-0007", name: "Value Leader" }], years: [2026], months: ["2026-01"], date_min: "2026-01-01", date_max: "2026-02-28" }),
    productDetail: () => Promise.resolve({
      id: 8,
      sku: "SKU-0008",
      name: "Quantity Leader",
      current_stock: 80,
      unit_cost_paise: 1000,
      unit_price_paise: 1500,
      reorder_recommendation: { suggested_qty: 12, rationale: "Cover the forecast.", trace_id: "trace-123" },
    }),
    predictiveOverview: (params?: { horizon_days?: number; category?: string }) =>
      Promise.resolve({
        ...predictiveOverviewMock,
        horizon_days: Number(params?.horizon_days ?? 28),
        kpis: {
          ...predictiveOverviewMock.kpis,
          expected_demand_units: {
            ...predictiveOverviewMock.kpis.expected_demand_units,
            value: params?.category === "Dairy" ? 88 : 420,
          },
        },
      }),
    predictiveDemand: () =>
      Promise.resolve({
        ready: true,
        forecast_as_of: "2026-11-01",
        series: [
          { date: "2026-10-25", actual_units: 5, is_forecast: false },
          { date: "2026-11-02", p50: 8, p10: 6, p90: 10, is_forecast: true },
        ],
        interval_note: "Heuristic cohort band.",
      }),
    predictiveProjection: () =>
      Promise.resolve({
        ready: true,
        forecast_as_of: "2026-11-01",
        mode: "no_reorder",
        series: [{ date: "2026-11-02", projected_inventory_value_paise: 250000, is_forecast: true }],
        projection_note: "Simulated path",
      }),
    predictiveRisks: () =>
      Promise.resolve({
        ready: true,
        distribution: { high: 2, moderate: 1, low: 3 },
        aggregation_note: "Stockout probabilities are never summed.",
        products: [],
        excess: { items: [], proxy_definition: "Cover proxy", modeled_risk_definition: "Modeled excess" },
      }),
    predictiveRecommendations: () =>
      Promise.resolve({
        ready: true,
        forecast_as_of: "2026-11-01",
        total_recommended_spend_paise: 48000,
        ranking_rule: "Not an opaque AI score.",
        items: [],
        insights: [{ id: "a", text: "High stockout risk SKUs have open recommendations." }],
      }),
    predictiveExplain: () =>
      Promise.resolve({
        ready: true,
        product: { product_id: 7, sku: "SKU-0007", name: "Value Leader", stock_on_hand: 4 },
        comparison: {
          no_reorder: { series: [{ date: "2026-11-02", projected_inventory_value_paise: 100000 }], ending_inventory_value_paise: 100000, total_unmet_demand_units: 5 },
          recommended: { series: [{ date: "2026-11-02", projected_inventory_value_paise: 120000 }], ending_inventory_value_paise: 120000, total_unmet_demand_units: 1 },
        },
      }),
    predictiveDataQuality: () =>
      Promise.resolve({
        ready: true,
        stale_risk_count: 2,
        freshness: { status: "partial", stale_risk_count: 2 },
        forecast_coverage: { covered: 5, selected: 6 },
        model_versions: [{ agent_name: "demand_interval", version: "1.0.0" }],
        limitations: ["GET predictive endpoints never retrain models."],
      }),
  },
}));

afterEach(() => cleanup());

describe("inventory analytics", () => {
  it("switches ranking and opens a product from the list", async () => {
    render(
      <MemoryRouter initialEntries={["/analytics"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Value Leader")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /^Quantity$/ }));
    expect(await screen.findByText("Quantity Leader")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Quantity Leader/i }));
    expect(await screen.findByRole("button", { name: "Simulate decision" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Explain recommendation" })).toBeTruthy();
  });

  it("filters KPIs from an ABC cell and restores them when cleared", async () => {
    render(
      <MemoryRouter initialEntries={["/analytics"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Reconstruction quality")).toBeTruthy();
    expect(screen.getByText("Historical as-of-period, stock on 2026-02-28. Current operational stock ₹2,500")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /AX/ }));
    expect(await screen.findByText("₹4,242")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear cell" }));
    expect(await screen.findByText("Historical as-of-period, stock on 2026-02-28. Current operational stock ₹2,500")).toBeTruthy();
  });

  it("restores a deep link and supports going back from a month", async () => {
    function Harness() {
      const navigate = useNavigate();
      return (
        <>
          <button type="button" onClick={() => navigate(-1)}>History back</button>
          <InventoryAnalytics />
        </>
      );
    }
    render(
      <MemoryRouter initialEntries={["/analytics?cell=AX&category=Dairy"]}>
        <Harness />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("button", { name: /AX/, pressed: true })).toBeTruthy();
    expect((screen.getByLabelText("Category") as HTMLSelectElement).value).toBe("Dairy");
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(await screen.findByRole("button", { name: /AX/, pressed: false })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "History back" }));
    expect(await screen.findByRole("button", { name: /AX/, pressed: true })).toBeTruthy();
  });

  it("navigates workspace tabs via segmented control", async () => {
    render(
      <MemoryRouter initialEntries={["/analytics"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    await screen.findByText("Reconstruction quality");
    fireEvent.click(screen.getByRole("button", { name: "Predictive Intelligence" }));
    expect(await screen.findByText("Forecast provenance")).toBeTruthy();
    expect(await screen.findByText("6 / 6 SKUs covered")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));
    expect(await screen.findByText("Reconstruction quality")).toBeTruthy();
  });

  it("renders predictive KPI values from the overview API", async () => {
    render(
      <MemoryRouter initialEntries={["/analytics?tab=predictive"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    expect(await screen.findByText("420")).toBeTruthy();
    expect(screen.getByText("Forecast as-of")).toBeTruthy();
    expect(screen.getByText("2026-11-01")).toBeTruthy();
  });

  it("shows unavailable state when forecasts are missing", async () => {
    const { api } = await import("../api/client");
    vi.spyOn(api, "predictiveOverview").mockResolvedValueOnce({
      ready: false,
      note: "No forecasts",
      kpis: { expected_demand_units: { unavailable_reason: "Missing rows" } },
    });
    render(
      <MemoryRouter initialEntries={["/analytics?tab=predictive"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Forecasts unavailable")).toBeTruthy();
  });

  it("refetches predictive overview when horizon changes", async () => {
    const { api } = await import("../api/client");
    const spy = vi.spyOn(api, "predictiveOverview");
    render(
      <MemoryRouter initialEntries={["/analytics?tab=predictive&horizon=28"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    await screen.findByText("420");
    fireEvent.click(screen.getAllByRole("button", { name: "14d" })[0]);
    await screen.findByText("Refreshing predictive workspace…");
    expect(spy.mock.calls.some((call) => String(call[0]?.horizon_days) === "14")).toBeTruthy();
  });

  it("refetches predictive data when category filter changes", async () => {
    const { api } = await import("../api/client");
    const spy = vi.spyOn(api, "predictiveOverview");
    render(
      <MemoryRouter initialEntries={["/analytics?tab=predictive&category=Dairy"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    expect(await screen.findByText("88")).toBeTruthy();
    expect(spy.mock.calls.some((call) => call[0]?.category === "Dairy")).toBeTruthy();
  });

  it("surfaces stale freshness warning on data quality tab", async () => {
    render(
      <MemoryRouter initialEntries={["/analytics?tab=quality"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/SKU risk rows may be stale/)).toBeTruthy();
  });

  it("keeps historical overview when predictive requests fail", async () => {
    const { api } = await import("../api/client");
    vi.spyOn(api, "predictiveOverview").mockRejectedValueOnce(new Error("predictive down"));
    render(
      <MemoryRouter initialEntries={["/analytics?tab=predictive"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    await screen.findByText(/Historical overview data is unchanged/);
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));
    expect(await screen.findByText("Historical as-of-period, stock on 2026-02-28. Current operational stock ₹2,500")).toBeTruthy();
  });

  it("selects a month from the keyboard-accessible chips", async () => {
    render(
      <MemoryRouter initialEntries={["/analytics"]}>
        <InventoryAnalytics />
      </MemoryRouter>,
    );
    const month = await screen.findByRole("button", { name: "2026-01" });
    fireEvent.click(month);
    expect(await screen.findByRole("button", { name: "2026-01", pressed: true })).toBeTruthy();
  });
});
