import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Performance } from "./Performance";
import type { RealDataSummary } from "../types/api";

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", ResizeObserverStub);

const performancePayload = {
  kpis: [
    { id: "wape", label: "WAPE", value: 0.2, unit: "%", measured: true },
    { id: "mae", label: "MAE", value: 1.2, measured: true },
    { id: "rmse", label: "RMSE", value: 2.1, measured: true },
    { id: "cov", label: "Coverage", value: 0.8, unit: "ratio", measured: true },
  ],
  baseline_comparison: [{ name: "demand", wape: 0.2 }],
  backtest_series: [{ date: "2026-10-01", actual: 3, predicted: 2.5 }],
  coverage: { nominal: "p10–p90 (80%)", empirical: 0.8, pinball_loss: 0.1 },
  model_versions: [{ name: "demand", version: "v1", status: "ready", source: "local" }],
  business_simulation: { label: "sim", rows: [] },
  evaluation_mode: "rolling_one_step_holdout",
};

const realSummaryReady: RealDataSummary = {
  experiment_id: "REAL_RETAIL_UCI",
  dataset_name: "Online Retail",
  attribution: "Daqing Chen",
  source_url: "https://archive.ics.uci.edu/dataset/352/online+retail",
  doi: "https://doi.org/10.24432/C5BW33",
  license: "CC BY 4.0",
  currency: "GBP",
  ready: true,
  status: {
    experiment_id: "REAL_RETAIL_UCI",
    raw_xlsx_present: true,
    daily_sales_present: true,
    splits_present: true,
    models_present: true,
    metrics_present: true,
    ready_for_ui: true,
  },
  metrics: {
    ml: { wape: 0.661, mae: 25.9, rmse: 89.4 },
    evaluation_mode: "rolling_one_step_ahead",
    model_version: "real_uci_v1",
    interval: { empirical_coverage_p10_p90: 0.83, mean_interval_width: 52.8 },
    best_wape_method: "hist_gradient_boosting",
    n_test_rows: 2800,
    n_skus: 100,
  },
  split_summary: {
    boundaries: {
      train_start: "2010-12-01",
      train_end: "2011-10-14",
      val_start: "2011-10-15",
      val_end: "2011-11-11",
      test_start: "2011-11-12",
      test_end: "2011-12-09",
    },
    sku_selection: { n_selected: 100 },
  },
  limitations: ["Observed sales are not unconstrained true demand."],
};

const realDataSummaryMock = vi.fn(async (): Promise<RealDataSummary> => realSummaryReady);

vi.mock("../hooks/useApi", () => ({
  useApi: () => ({
    data: performancePayload,
    loading: false,
    error: null,
    offline: false,
    reload: vi.fn(),
  }),
}));

vi.mock("../api/client", () => ({
  ApiError: class extends Error {
    status = 404;
  },
  api: {
    performance: vi.fn(),
    realDataSummary: () => realDataSummaryMock(),
    realDataMetadata: vi.fn(async () => ({
      experiment_id: "REAL_RETAIL_UCI",
      dataset_name: "Online Retail",
      source_url: realSummaryReady.source_url,
      doi: realSummaryReady.doi,
      license: "CC BY 4.0",
      attribution: "Daqing Chen",
      currency: "GBP",
      raw_columns: ["InvoiceNo", "StockCode"],
      daily_sales_columns: ["date", "stock_code", "units_sold"],
      provenance_label: "REAL_RETAIL_UCI",
      synthetic_label: "SYNTHETIC_DEMO",
      training: { model_version: "real_uci_v1" },
    })),
    realDataMetrics: vi.fn(async () => realSummaryReady.metrics),
    realDataBaselines: vi.fn(async () => ({
      rows: [
        { method: "hist_gradient_boosting", wape: 0.661, mae: 25.9, rmse: 89.4 },
        { method: "seasonal_naive_7", wape: 0.956, mae: 37.4, rmse: 108 },
        { method: "moving_average_28", wape: 0.887, mae: 34.7, rmse: 90.8 },
      ],
    })),
    realDataProducts: vi.fn(async () => ({
      products: [{ stock_code: "85123A", total_actual: 100 }],
    })),
    realDataPredictions: vi.fn(async () => ({
      rows: [
        {
          date: "2011-11-12",
          stock_code: "85123A",
          actual_units: 10,
          predicted_units: 8,
          seasonal_naive_units: 7,
          p10_units: 2,
          p50_units: 8,
          p90_units: 15,
        },
      ],
    })),
  },
}));

describe("Performance evaluation source switch", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    realDataSummaryMock.mockReset();
    realDataSummaryMock.mockResolvedValue(realSummaryReady);
  });

  it("defaults to synthetic demo and can switch to real retail", async () => {
    render(<Performance />);
    const source = screen.getByLabelText("Evaluation source") as HTMLSelectElement;
    expect(source.value).toBe("synthetic");
    expect(screen.getByText(/Measured evaluation on synthetic data/i)).toBeTruthy();

    fireEvent.change(source, { target: { value: "real" } });

    await waitFor(() => {
      expect(screen.getByText(/REAL_RETAIL_UCI/i)).toBeTruthy();
    });
    expect(screen.getByText(/Holdout WAPE/i)).toBeTruthy();
    expect(screen.getAllByText(/CC BY 4.0/i).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Real retail SKU")).toBeTruthy();
  });

  it("shows missing experiment empty state when not ready", async () => {
    realDataSummaryMock.mockResolvedValue({
      ...realSummaryReady,
      ready: false,
      status: { ...realSummaryReady.status, ready_for_ui: false },
      metrics: undefined,
    });

    render(<Performance />);
    fireEvent.change(screen.getByLabelText("Evaluation source"), {
      target: { value: "real" },
    });
    await waitFor(() => {
      expect(screen.getByText(/Real retail evaluation not ready/i)).toBeTruthy();
    });
  });
});
