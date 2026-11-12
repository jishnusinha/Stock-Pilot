import { describe, expect, it } from "vitest";
import { analyticsFetchKey, readAnalyticsQuery, writeAnalyticsQuery } from "./analyticsQuery";

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
});
