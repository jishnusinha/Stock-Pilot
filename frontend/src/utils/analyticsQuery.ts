export type RankMode = "value" | "quantity";

export type AnalyticsTab = "overview" | "predictive" | "decisions" | "quality";

export type PredictiveHorizon = "7" | "14" | "28";

export type ProjectionMode = "no_reorder" | "recommended";

export type AnalyticsQuery = {
  from?: string;
  to?: string;
  year?: string;
  month?: string;
  category?: string;
  supplier?: string;
  product?: string;
  rank: RankMode;
  cell?: string;
  tab?: AnalyticsTab;
  horizon?: PredictiveHorizon;
  mode?: ProjectionMode;
};

const TABS: AnalyticsTab[] = ["overview", "predictive", "decisions", "quality"];
const HORIZONS: PredictiveHorizon[] = ["7", "14", "28"];
const MODES: ProjectionMode[] = ["no_reorder", "recommended"];

const EMPTY: AnalyticsQuery = { rank: "value", tab: "overview", horizon: "28", mode: "no_reorder" };

function parseTab(raw: string | null): AnalyticsTab {
  if (raw && TABS.includes(raw as AnalyticsTab) && raw !== "overview") return raw as AnalyticsTab;
  return "overview";
}

function parseHorizon(raw: string | null): PredictiveHorizon {
  if (raw && HORIZONS.includes(raw as PredictiveHorizon)) return raw as PredictiveHorizon;
  return "28";
}

function parseMode(raw: string | null): ProjectionMode {
  if (raw && MODES.includes(raw as ProjectionMode)) return raw as ProjectionMode;
  return "no_reorder";
}

export function readAnalyticsQuery(params: URLSearchParams): AnalyticsQuery {
  const rank = params.get("rank") === "quantity" ? "quantity" : "value";
  return {
    from: params.get("from") || undefined,
    to: params.get("to") || undefined,
    year: params.get("year") || undefined,
    month: params.get("month") || undefined,
    category: params.get("category") || undefined,
    supplier: params.get("supplier") || undefined,
    product: params.get("product") || undefined,
    rank,
    cell: params.get("cell") || undefined,
    tab: parseTab(params.get("tab")),
    horizon: parseHorizon(params.get("horizon")),
    mode: parseMode(params.get("mode")),
  };
}

export function writeAnalyticsQuery(query: AnalyticsQuery): URLSearchParams {
  const params = new URLSearchParams();
  const entries: [string, string | undefined][] = [
    ["from", query.from],
    ["to", query.to],
    ["year", query.year],
    ["month", query.month],
    ["category", query.category],
    ["supplier", query.supplier],
    ["product", query.product],
    ["rank", query.rank === "quantity" ? "quantity" : undefined],
    ["cell", query.cell],
    ["tab", query.tab && query.tab !== "overview" ? query.tab : undefined],
    ["horizon", query.horizon && query.horizon !== "28" ? query.horizon : undefined],
    ["mode", query.mode && query.mode !== "no_reorder" ? query.mode : undefined],
  ];
  entries.forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return params;
}

export function clearAnalyticsQuery(): AnalyticsQuery {
  return { ...EMPTY };
}

/** Historical cohort + filters; ignores predictive horizon/mode/tab. */
export function analyticsFetchKey(query: AnalyticsQuery): string {
  return [query.from, query.to, query.year, query.month, query.category, query.supplier, query.product, query.cell].join("|");
}

/** Predictive layer refetch key (filters + horizon + mode). */
export function predictiveFetchKey(query: AnalyticsQuery): string {
  return [analyticsFetchKey(query), query.horizon ?? "28", query.mode ?? "no_reorder"].join("|");
}
