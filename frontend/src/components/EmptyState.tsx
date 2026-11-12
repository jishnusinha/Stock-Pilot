import { Inbox } from "lucide-react";

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message?: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      className="card"
      style={{ textAlign: "center", padding: "48px 24px", color: "var(--color-text-muted)" }}
    >
      <Inbox size={40} strokeWidth={1.25} style={{ marginBottom: 16, opacity: 0.5 }} />
      <h2 style={{ color: "var(--color-text)" }}>{title}</h2>
      {message ? <p>{message}</p> : null}
      {action ? <div style={{ marginTop: 16 }}>{action}</div> : null}
    </div>
  );
}
