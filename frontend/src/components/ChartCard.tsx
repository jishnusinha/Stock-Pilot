import type { ReactNode } from "react";

export function ChartCard({
  title,
  subtitle,
  actions,
  children,
  ariaLabel,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  ariaLabel?: string;
}) {
  return (
    <figure className="card" aria-label={ariaLabel ?? title} style={{ margin: 0 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 16,
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h2 className="card-title" style={{ margin: 0 }}>
            {title}
          </h2>
          {subtitle ? (
            <p style={{ fontSize: 12, color: "var(--color-text-muted)", margin: "4px 0 0" }}>
              {subtitle}
            </p>
          ) : null}
        </div>
        {actions}
      </div>
      {children}
    </figure>
  );
}
