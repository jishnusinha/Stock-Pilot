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
