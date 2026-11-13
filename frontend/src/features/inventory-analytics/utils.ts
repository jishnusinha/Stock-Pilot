import type { AnalyticsParams } from "../../types/api";
import type { AnalyticsQuery } from "../../utils/analyticsQuery";

export function cohortParams(query: AnalyticsQuery, extra: Partial<AnalyticsParams> = {}): AnalyticsParams {
  return {
    date_from: query.from,
    date_to: query.to,
    year: query.year,
    month: query.month,
    category: query.category,
    supplier_id: query.supplier,
    product_id: query.product,
    segment: query.cell,
    ...extra,
  };
}

/** Cohort filters plus predictive controls (horizon / projection mode). */
export function predictiveParams(query: AnalyticsQuery, extra: Partial<AnalyticsParams> = {}): AnalyticsParams {
  return cohortParams(query, {
    horizon_days: Number(query.horizon ?? "28"),
    mode: query.mode ?? "no_reorder",
    ...extra,
  });
}

export function compactPaise(paise: number): string {
  const rupees = paise / 100;
  if (Math.abs(rupees) >= 100000) return `₹${(rupees / 100000).toFixed(1)}L`;
  if (Math.abs(rupees) >= 1000) return `₹${(rupees / 1000).toFixed(1)}k`;
  return `₹${Math.round(rupees)}`;
}

export function isPartialMonth(days?: number | null): boolean {
  return days != null && days > 0 && days < 28;
}
