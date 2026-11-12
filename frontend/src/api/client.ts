import type {
  AdjustStockRequest,
  AgentCard,
  AgentRunSummary,
  AgentRunTrace,
  DashboardResponse,
  HealthResponse,
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
} from "../types/api";

const BASE =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

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
