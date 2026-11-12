import type { ReactNode } from "react";

type Variant = "default" | "mint" | "risk" | "warning" | "muted";

const styles: Record<Variant, React.CSSProperties> = {
  default: { background: "#f3f4f6", color: varMuted() },
  mint: { background: "var(--color-mint)", color: "var(--color-primary)" },
  risk: { background: "var(--color-risk-bg)", color: "var(--color-risk)" },
  warning: { background: "var(--color-warning-bg)", color: "var(--color-warning)" },
  muted: { background: "#eef0ec", color: "var(--color-text-muted)" },
};

function varMuted() {
  return "var(--color-text-muted)";
}

export function Badge({
  children,
  variant = "default",
}: {
  children: ReactNode;
  variant?: Variant;
}) {
  return (
    <span
      className="badge"
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 8px",
        borderRadius: "var(--radius-pill)",
        fontSize: 12,
        fontWeight: 500,
        ...styles[variant],
      }}
    >
      {children}
    </span>
  );
}

export function RiskBadge({ level }: { level: string }) {
  const l = level.toLowerCase();
  if (l === "high") return <Badge variant="risk">High risk</Badge>;
  if (l === "medium") return <Badge variant="warning">Medium</Badge>;
  return <Badge variant="mint">Low</Badge>;
}
