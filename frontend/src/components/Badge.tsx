import type { ReactNode } from "react";

type Variant = "default" | "mint" | "risk" | "warning" | "muted" | "info";

export function Badge({
  children,
  variant = "default",
}: {
  children: ReactNode;
  variant?: Variant;
}) {
  return <span className={`badge badge-${variant}`}>{children}</span>;
}

export function RiskBadge({ level }: { level: string }) {
  const l = level.toLowerCase();
  if (l === "high") return <Badge variant="risk">High</Badge>;
  if (l === "medium") return <Badge variant="warning">Medium</Badge>;
  if (l === "low") return <Badge variant="mint">Low</Badge>;
  if (l === "overstock") return <Badge variant="info">Overstock</Badge>;
  return <Badge variant="muted">{level}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (s === "pending" || s === "draft") return <Badge variant="warning">Pending</Badge>;
  if (s === "approved") return <Badge variant="mint">Approved</Badge>;
  if (s === "rejected" || s === "error" || s === "failed") return <Badge variant="risk">Rejected</Badge>;
  if (s === "received" || s === "ok" || s === "active") return <Badge variant="info">{status}</Badge>;
  return <Badge variant="muted">{status}</Badge>;
}
