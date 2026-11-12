import { describe, expect, it } from "vitest";
import { dependencyPath, edgeOnPath } from "./orchestration";

describe("orchestration graph", () => {
  it("connects upstream signals to demand and keeps supplier ETA on the optimizer path", () => {
    const demand = dependencyPath("demand");
    expect(demand.has("sales_anomaly")).toBe(true);
    expect(demand.has("product_similarity")).toBe(true);
    expect(demand.has("optimizer")).toBe(true);
    expect(demand.has("supplier_eta")).toBe(false);
    const optimizer = dependencyPath("optimizer");
    expect(optimizer.has("supplier_eta")).toBe(true);
    expect(optimizer.has("demand")).toBe(true);
  });

  it("does not highlight an unrelated edge", () => {
    expect(edgeOnPath("calendar_effect", "demand", "supplier_eta")).toBe(false);
    expect(edgeOnPath("supplier_eta", "optimizer", "supplier_eta")).toBe(true);
  });
});
