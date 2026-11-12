import type { ReactNode } from "react";
import { Badge } from "./Badge";

export function KpiCard({
  label,
  value,
  sublabel,
  trend,
  trendVariant = "mint",
  icon,
  tone = "ok",
  onClick,
  selected,
}: {
  label: string;
  value: ReactNode;
  sublabel?: ReactNode;
  trend?: string | null;
  trendVariant?: "mint" | "risk" | "warning" | "muted" | "info";
  icon?: ReactNode;
  tone?: "ok" | "warn" | "risk" | "info";
  onClick?: () => void;
  selected?: boolean;
}) {
  const iconClass =
    tone === "warn" ? "kpi-icon warn" : tone === "risk" ? "kpi-icon risk" : tone === "info" ? "kpi-icon info" : "kpi-icon";
  const body = (
    <>
      <div className="kpi-top">
        <div className="kpi-label">{label}</div>
        {icon ? <span className={iconClass}>{icon}</span> : null}
      </div>
      <div className="kpi-value tabular">{value}</div>
      <div className="kpi-foot">
        {trend ? <Badge variant={trendVariant}>{trend}</Badge> : null}
        {sublabel ? <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{sublabel}</span> : null}
      </div>
    </>
  );
  if (onClick) {
    return (
      <button type="button" className={`card kpi-card buttonish${selected ? " selected" : ""}`} onClick={onClick}>
        {body}
      </button>
    );
  }
  return <article className="card kpi-card">{body}</article>;
}
