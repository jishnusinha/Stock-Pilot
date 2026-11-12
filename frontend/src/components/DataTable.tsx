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
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--color-border)", textAlign: "left" }}>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{
                  padding: "10px 12px",
                  fontWeight: 600,
                  color: "var(--color-text-muted)",
                  textAlign: col.align ?? "left",
                }}
              >
                {col.sortable && onSort ? (
                  <button
                    type="button"
                    className="btn-sort"
                    onClick={() => onSort(col.key)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      fontWeight: 600,
                      color: "inherit",
                      padding: 0,
                    }}
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
                onClick={() => onSelect?.(row)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect?.(row);
                  }
                }}
                tabIndex={onSelect ? 0 : undefined}
                style={{
                  borderBottom: "1px solid var(--color-border)",
                  cursor: onSelect ? "pointer" : "default",
                  background: selected ? "var(--color-mint)" : "transparent",
                }}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    style={{ padding: "12px", textAlign: col.align ?? "left" }}
                    className="tabular"
                  >
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
