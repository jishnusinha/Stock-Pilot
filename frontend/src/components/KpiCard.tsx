import type { ReactNode } from "react";
import { Badge } from "./Badge";

export function KpiCard({
  label,
  value,
  sublabel,
  trend,
  trendVariant = "mint",
}: {
  label: string;
  value: ReactNode;
  sublabel?: string;
  trend?: string | null;
  trendVariant?: "mint" | "risk" | "warning" | "muted";
}) {
  return (
    <div className="card kpi-card">
      <div style={{ color: "var(--color-text-muted)", fontSize: 13, marginBottom: 8 }}>
        {label}
      </div>
      <div
        className="tabular"
        style={{ fontSize: "1.5rem", fontWeight: 600, marginBottom: 4 }}
      >
        {value}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        {trend ? <Badge variant={trendVariant}>{trend}</Badge> : null}
        {sublabel ? (
          <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{sublabel}</span>
        ) : null}
      </div>
    </div>
  );
}
