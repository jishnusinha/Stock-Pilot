import type { ReactNode } from "react";

export type Column<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortable?: boolean;
  align?: "left" | "right";
};

function rowKey(row: object, index: number): string | number {
  const r = row as Record<string, unknown>;
  if (r.id != null) return r.id as string | number;
  if (typeof r.trace_id === "string") return r.trace_id;
  if (typeof r.product_id === "number") return r.product_id;
  if (typeof r.name === "string") return r.name;
  return index;
}

export function DataTable<T extends object>({
  columns,
  rows,
  selectedId,
  onSelect,
  sortKey,
  sortDir,
  onSort,
}: {
  columns: Column<T>[];
  rows: T[];
  selectedId?: number | string | null;
  onSelect?: (row: T) => void;
  sortKey?: string;
  sortDir?: "asc" | "desc";
  onSort?: (key: string) => void;
}) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} style={{ textAlign: col.align ?? "left" }}>
                {col.sortable && onSort ? (
                  <button
                    type="button"
                    className="btn-sort"
                    onClick={() => onSort(col.key)}
                    aria-sort={sortKey === col.key ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                  >
                    {col.header}
                    {sortKey === col.key ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                  </button>
                ) : (
                  col.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const id = rowKey(row, i);
            const selected = selectedId != null && id === selectedId;
            return (
              <tr
                key={String(id)}
                className={`${onSelect ? "clickable" : ""}${selected ? " selected" : ""}`}
                onClick={() => onSelect?.(row)}
                onKeyDown={(e) => {
                  if (!onSelect) return;
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(row);
                  }
                }}
                tabIndex={onSelect ? 0 : undefined}
                aria-selected={onSelect ? selected : undefined}
              >
                {columns.map((col) => (
                  <td key={col.key} style={{ textAlign: col.align ?? "left" }} className="tabular">
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function TablePagination({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  onPageSize?: (size: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return (
    <div className="table-foot">
      <span className="tabular">
        Showing {start}–{end} of {total}
      </span>
      <div className="pager">
        {onPageSize ? (
          <label className="tabular" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            Rows
            <select
              className="select"
              style={{ width: 72 }}
              value={pageSize}
              aria-label="Rows per page"
              onChange={(e) => onPageSize(Number(e.target.value))}
            >
              {[10, 20, 50].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <button type="button" className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <span className="tabular">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
