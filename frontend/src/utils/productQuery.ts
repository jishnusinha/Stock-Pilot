export type ProductQueryState = {
  page: number;
  pageSize: number;
  search?: string;
  category?: string;
  risk?: string;
  supplierId?: string;
  stockHealth?: string;
  sort: string;
  sortDir: "asc" | "desc";
};

export function productListQuery(
  state: ProductQueryState,
): Record<string, string | number | undefined> {
  return {
    page: state.page,
    page_size: state.pageSize,
    search: state.search || undefined,
    category: state.category || undefined,
    risk: state.risk || undefined,
    supplier_id: state.supplierId || undefined,
    stock_health: state.stockHealth || undefined,
    sort: state.sort,
    direction: state.sortDir,
  };
}
