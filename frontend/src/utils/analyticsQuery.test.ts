import { describe, expect, it } from "vitest";
import { analyticsFetchKey, predictiveFetchKey, readAnalyticsQuery, writeAnalyticsQuery } from "./analyticsQuery";

describe("analytics query", () => {
  it("round-trips filters and keeps value rank out of the url", () => {
    const params = writeAnalyticsQuery({
      year: "2026",
      month: "11",
      category: "Dairy",
      supplier: "3",
      rank: "value",
    });
    expect(params.get("rank")).toBeNull();
    expect(params.get("category")).toBe("Dairy");
    const query = readAnalyticsQuery(params);
    expect(query.rank).toBe("value");
    expect(query.month).toBe("11");
    expect(analyticsFetchKey(query)).toContain("Dairy");
  });

  it("keeps quantity rank", () => {
    const params = writeAnalyticsQuery({ rank: "quantity", cell: "AZ" });
    expect(readAnalyticsQuery(params).rank).toBe("quantity");
    expect(readAnalyticsQuery(params).cell).toBe("AZ");
  });

  it("round-trips tab, horizon, and mode", () => {
    const params = writeAnalyticsQuery({
      rank: "value",
      tab: "predictive",
      horizon: "14",
      mode: "recommended",
      product: "7",
    });
    expect(params.get("tab")).toBe("predictive");
    expect(params.get("horizon")).toBe("14");
    expect(params.get("mode")).toBe("recommended");
    const query = readAnalyticsQuery(params);
    expect(query.tab).toBe("predictive");
    expect(query.horizon).toBe("14");
    expect(query.mode).toBe("recommended");
  });

  it("omits default tab, horizon, and mode from url", () => {
    const params = writeAnalyticsQuery({ rank: "value", tab: "overview", horizon: "28", mode: "no_reorder" });
    expect(params.get("tab")).toBeNull();
    expect(params.get("horizon")).toBeNull();
    expect(params.get("mode")).toBeNull();
  });

  it("does not change historical fetch key when horizon or mode changes", () => {
    const base = writeAnalyticsQuery({ category: "Dairy", rank: "value" });
    const query = readAnalyticsQuery(base);
    const withPredictive = readAnalyticsQuery(
      writeAnalyticsQuery({ ...query, horizon: "7", mode: "recommended", tab: "predictive" }),
    );
    expect(analyticsFetchKey(query)).toBe(analyticsFetchKey(withPredictive));
    expect(predictiveFetchKey(withPredictive)).not.toBe(predictiveFetchKey(query));
  });
});
