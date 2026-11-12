import { describe, expect, it } from "vitest";
import { productListQuery } from "./productQuery";

describe("product list query", () => {
  it("sends the sort direction the table is showing", () => {
    const query = productListQuery({
      page: 2,
      pageSize: 20,
      search: "granola",
      category: "Snacks",
      risk: "high",
      supplierId: "4",
      stockHealth: "low",
      sort: "stock",
      sortDir: "desc",
    });
    expect(query.direction).toBe("desc");
    expect(query.sort).toBe("stock");
    expect(query.stock_health).toBe("low");
    expect(query.page).toBe(2);
  });
});
