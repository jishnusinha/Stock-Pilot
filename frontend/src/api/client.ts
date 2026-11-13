import type {
  AdjustStockRequest,
  AgentCard,
  AgentRunSummary,
  AgentRunTrace,
  AnalyticsFilters,
  AnalyticsMonth,
  AnalyticsOverview,
  AnalyticsParams,
  AbcCell,
  AbcProduct,
  CalendarItem,
  DashboardResponse,
  HealthResponse,
  MovementReport,
  RankedProduct,
  SlowItem,
  SupplierScore,
  PerformanceResponse,
  ProductCreateRequest,
  ProductDetail,
  ProductUpdateRequest,
  InventorySummary,
  ProductsListResponse,
  ScenarioDetail,
  ReorderCreateRequest,
  ReorderRow,
  SaveScenarioRequest,
  ScenarioSummary,
  SimulateRequest,
  SimulateResponse,
  Supplier,
  PredictiveOverview,
  PredictiveDemand,
  PredictiveProjection,
  PredictiveRisks,
  PredictiveRecommendations,
  PredictiveExplain,
  PredictiveDataQuality,
} from "../types/api";

const BASE =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

function withQuery(path: string, params: AnalyticsParams = {}): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") q.set(key, String(value));
  });
  const text = q.toString();
  return `${path}${text ? `?${text}` : ""}`;
}

function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (BASE) return `${BASE}${p}`;
  return p;
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) return {} as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(res.status, "Invalid JSON response", text);
  }
}

export async function fetchJson<T>(
  path: string,
  init?: RequestInit & { signal?: AbortSignal },
): Promise<T> {
  const res = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    let parsed: unknown = body;
    try {
      parsed = JSON.parse(body);
    } catch {
      /* ignore */
    }
    const msg =
      typeof parsed === "object" &&
      parsed &&
      "detail" in parsed &&
      typeof (parsed as { detail: unknown }).detail === "string"
        ? (parsed as { detail: string }).detail
        : res.statusText || `HTTP ${res.status}`;
    throw new ApiError(res.status, msg, parsed);
  }
  return parseJson<T>(res);
}

export const api = {
  health(signal?: AbortSignal) {
    return fetchJson<HealthResponse>("/api/health", { signal });
  },

  dashboard(signal?: AbortSignal) {
    return fetchJson<DashboardResponse>("/api/dashboard", { signal });
  },

  inventorySummary(signal?: AbortSignal) {
    return fetchJson<InventorySummary>("/api/inventory/summary", { signal });
  },

  products(
    params: Record<string, string | number | undefined>,
    signal?: AbortSignal,
  ) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") q.set(k, String(v));
    });
    const qs = q.toString();
    return fetchJson<ProductsListResponse>(
      `/api/products${qs ? `?${qs}` : ""}`,
      { signal },
    );
  },

  productDetail(id: number, signal?: AbortSignal) {
    return fetchJson<ProductDetail>(`/api/products/${id}`, { signal });
  },

  adjustStock(id: number, body: AdjustStockRequest, signal?: AbortSignal) {
    return fetchJson<ProductDetail>(`/api/products/${id}/adjust-stock`, {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    });
  },

  createProduct(body: ProductCreateRequest, signal?: AbortSignal) {
    return fetchJson<ProductDetail>("/api/products", {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    });
  },

  updateProduct(id: number, body: ProductUpdateRequest, signal?: AbortSignal) {
    return fetchJson<ProductDetail>(`/api/products/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      signal,
    });
  },

  deleteProduct(id: number, signal?: AbortSignal) {
    return fetchJson<{ ok: boolean; id: number }>(`/api/products/${id}`, {
      method: "DELETE",
      signal,
    });
  },

  suppliers(signal?: AbortSignal) {
    return fetchJson<Supplier[]>("/api/suppliers", { signal });
  },

  forecasts(productId: number, signal?: AbortSignal) {
    return fetchJson<{ series: unknown[]; as_of?: string }>(
      `/api/forecasts/${productId}`,
      { signal },
    );
  },

  simulate(body: SimulateRequest, signal?: AbortSignal) {
    return fetchJson<SimulateResponse>("/api/simulate", {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    });
  },

  saveScenario(body: SaveScenarioRequest, signal?: AbortSignal) {
    return fetchJson<ScenarioSummary>("/api/scenarios", {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    });
  },

  listScenarios(signal?: AbortSignal) {
    return fetchJson<ScenarioSummary[]>("/api/scenarios", { signal });
  },

  getScenario(id: number, signal?: AbortSignal) {
    return fetchJson<ScenarioDetail>(`/api/scenarios/${id}`, { signal });
  },

  proposeRecommendation(id: number, signal?: AbortSignal) {
    return fetchJson<ReorderRow>(`/api/recommendations/${id}/propose`, {
      method: "POST",
      signal,
    });
  },

  reorders(signal?: AbortSignal) {
    return fetchJson<ReorderRow[]>("/api/reorders", { signal });
  },

  createReorder(body: ReorderCreateRequest, signal?: AbortSignal) {
    return fetchJson<ReorderRow>("/api/reorders", {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    });
  },

  approveReorder(id: number, signal?: AbortSignal) {
    return fetchJson<ReorderRow>(`/api/reorders/${id}/approve`, {
      method: "POST",
      signal,
    });
  },

  rejectReorder(id: number, signal?: AbortSignal) {
    return fetchJson<ReorderRow>(`/api/reorders/${id}/reject`, {
      method: "POST",
      signal,
    });
  },

  receiveReorder(id: number, signal?: AbortSignal) {
    return fetchJson<ReorderRow>(`/api/reorders/${id}/receive`, {
      method: "POST",
      signal,
    });
  },

  agents(signal?: AbortSignal) {
    return fetchJson<AgentCard[]>("/api/agents", { signal });
  },

  agentRuns(params?: { page?: number; page_size?: number }, signal?: AbortSignal) {
    const q = new URLSearchParams();
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    const qs = q.toString();
    return fetchJson<AgentRunSummary[]>(
      `/api/agent-runs${qs ? `?${qs}` : ""}`,
      { signal },
    );
  },

  getTrace(traceId: string, signal?: AbortSignal) {
    return fetchJson<AgentRunTrace>(`/api/agent-runs/${traceId}`, { signal });
  },

  triggerRun(body: { product_id: number }, signal?: AbortSignal) {
    return fetchJson<AgentRunTrace>("/api/agent-runs/trigger", {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    });
  },

  performance(signal?: AbortSignal) {
    return fetchJson<PerformanceResponse>("/api/performance", { signal });
  },

  analyticsOverview(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<AnalyticsOverview>(withQuery("/api/analytics/overview", params), { signal });
  },
  analyticsTrend(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<{ ready: boolean; note?: string | null; months: AnalyticsMonth[] }>(
      withQuery("/api/analytics/inventory-trend", params),
      { signal },
    );
  },
  analyticsTurnover(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<{ ready: boolean; months: AnalyticsMonth[]; definition?: string; reference_target?: number }>(
      withQuery("/api/analytics/turnover", params),
      { signal },
    );
  },
  analyticsMovements(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<MovementReport>(withQuery("/api/analytics/movements", params), { signal });
  },
  analyticsTop(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<{ ready: boolean; by_value: RankedProduct[]; by_quantity: RankedProduct[] }>(
      withQuery("/api/analytics/top-products", params),
      { signal },
    );
  },
  analyticsSales(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<{ ready: boolean; months: AnalyticsMonth[]; definition?: string }>(
      withQuery("/api/analytics/inventory-sales", params),
      { signal },
    );
  },
  analyticsCategories(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<{
      ready: boolean;
      categories: {
        category: string;
        sku_count: number;
        inventory_value_paise: number;
        revenue_paise: number;
        value_share?: number | null;
      }[];
    }>(withQuery("/api/analytics/category-breakdown", params), { signal });
  },
  analyticsAbc(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<{
      ready: boolean;
      abc_rule?: string;
      xyz_rule?: string;
      cells: AbcCell[];
      products: AbcProduct[];
      total: number;
    }>(withQuery("/api/analytics/abc-xyz", params), { signal });
  },
  analyticsSlow(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<{ ready: boolean; definition?: string; as_of?: string | null; items: SlowItem[]; total: number }>(
      withQuery("/api/analytics/slow-moving", params),
      { signal },
    );
  },
  analyticsSuppliers(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<{
      ready: boolean;
      catalog_reliability_label?: string;
      simulated_label?: string;
      items: SupplierScore[];
    }>(withQuery("/api/analytics/suppliers", params), { signal });
  },
  analyticsFilters(signal?: AbortSignal) {
    return fetchJson<AnalyticsFilters>("/api/analytics/filters", { signal });
  },

  predictiveOverview(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<PredictiveOverview>(withQuery("/api/analytics/predictive/overview", params), { signal });
  },
  predictiveDemand(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<PredictiveDemand>(withQuery("/api/analytics/predictive/demand", params), { signal });
  },
  predictiveProjection(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<PredictiveProjection>(withQuery("/api/analytics/predictive/inventory-projection", params), { signal });
  },
  predictiveRisks(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<PredictiveRisks>(withQuery("/api/analytics/predictive/risks", params), { signal });
  },
  predictiveRecommendations(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<PredictiveRecommendations>(withQuery("/api/analytics/predictive/recommendations", params), { signal });
  },
  predictiveExplain(productId: number, signal?: AbortSignal) {
    return fetchJson<PredictiveExplain>(`/api/analytics/predictive/explain/${productId}`, { signal });
  },
  predictiveDataQuality(params: AnalyticsParams = {}, signal?: AbortSignal) {
    return fetchJson<PredictiveDataQuality>(withQuery("/api/analytics/predictive/data-quality", params), { signal });
  },
  reorderCalendar(signal?: AbortSignal) {
    return fetchJson<{ items: CalendarItem[]; dated_count: number; undated_count: number; note: string }>(
      "/api/reorders/calendar",
      { signal },
    );
  },

  async exportCsv(
    params: Record<string, string | number | undefined>,
    signal?: AbortSignal,
  ): Promise<Blob> {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") q.set(k, String(v));
    });
    const qs = q.toString();
    const res = await fetch(apiUrl(`/api/products/export.csv${qs ? `?${qs}` : ""}`), {
      signal,
    });
    if (!res.ok) {
      throw new ApiError(res.status, res.statusText);
    }
    return res.blob();
  },
};

export function isConnectionError(err: unknown): boolean {
  if (err instanceof TypeError) return true;
  if (err instanceof ApiError && err.status === 0) return true;
  return false;
}
