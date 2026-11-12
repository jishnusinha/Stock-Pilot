import { describe, expect, it } from "vitest";
import { windowHistory, withUncertaintyBand } from "./forecastBand";
import type { ForecastPoint } from "../types/api";

const rows: ForecastPoint[] = [
  { date: "2026-10-01", actual: 10, is_forecast: false, p10: 1, p90: 99 },
  { date: "2026-11-02", p50: 20, p10: 12, p90: 30, is_forecast: true },
  { date: "2026-11-03", p50: 21, p10: 40, p90: 15, is_forecast: true },
];

describe("uncertainty band", () => {
  it("draws one interval from p10 up to p90 and ignores history", () => {
    const banded = withUncertaintyBand(rows);
    expect(banded[0].bandBase).toBeNull();
    expect(banded[0].bandSpan).toBeNull();
    expect(banded[1].bandBase).toBe(12);
    expect(banded[1].bandSpan).toBe(18);
    expect(banded[2].bandSpan).toBe(0);
  });

  it("keeps the forecast tail when the history window is shortened", () => {
    const history = Array.from({ length: 5 }, (_, i) => ({
      date: `2026-10-0${i + 1}`,
      actual: i,
      is_forecast: false,
    }));
    const forecast = [{ date: "2026-11-02", p50: 4, is_forecast: true }];
    const windowed = windowHistory([...history, ...forecast], 2);
    expect(windowed).toHaveLength(3);
    expect(windowed.at(-1)?.is_forecast).toBe(true);
  });
});
