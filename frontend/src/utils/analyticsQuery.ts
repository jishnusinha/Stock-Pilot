export type RankMode = "value" | "quantity";

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
};

const EMPTY: AnalyticsQuery = { rank: "value" };

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
  ];
  entries.forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return params;
}

export function clearAnalyticsQuery(): AnalyticsQuery {
  return { ...EMPTY };
}

export function analyticsFetchKey(query: AnalyticsQuery): string {
  return [query.from, query.to, query.year, query.month, query.category, query.supplier, query.product].join("|");
}
