import type { ForecastPoint } from "../types/api";

export type BandPoint = ForecastPoint & {
  bandBase: number | null;
  bandSpan: number | null;
};

/** p10–p90 as a single interval: base at p10, height = p90 − p10. Not a stacked pair of areas. */
export function withUncertaintyBand(rows: ForecastPoint[]): BandPoint[] {
  return rows.map((p) => {
    const has =
      Boolean(p.is_forecast) && p.p10 != null && p.p90 != null && !Number.isNaN(p.p10) && !Number.isNaN(p.p90);
    if (!has) return { ...p, bandBase: null, bandSpan: null };
    const low = Number(p.p10);
    const high = Number(p.p90);
    return {
      ...p,
      bandBase: low,
      bandSpan: Math.max(0, high - low),
    };
  });
}

export function windowHistory(rows: ForecastPoint[], historyDays: number): ForecastPoint[] {
  const history = rows.filter((r) => !r.is_forecast);
  const forecast = rows.filter((r) => r.is_forecast);
  const days = Math.max(1, historyDays);
  return [...history.slice(-days), ...forecast];
}
