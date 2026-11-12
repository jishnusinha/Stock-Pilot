import { AlertTriangle, RefreshCw } from "lucide-react";

export function ErrorState({
  message,
  onRetry,
  offline,
}: {
  message: string;
  onRetry?: () => void;
  offline?: boolean;
}) {
  return (
    <div
      className="card"
      role="alert"
      style={{
        borderColor: offline ? "#ffc107" : "var(--color-risk)",
        background: offline ? "#fffbeb" : "var(--color-risk-bg)",
      }}
    >
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <AlertTriangle size={22} color="var(--color-risk)" />
        <div style={{ flex: 1 }}>
          <strong>{offline ? "Cannot reach API" : "Something went wrong"}</strong>
          <p style={{ margin: "8px 0", color: "var(--color-text-muted)" }}>{message}</p>
          {offline ? (
            <p style={{ fontSize: 13 }}>
              Start the backend at <code>http://127.0.0.1:8000</code> or set{" "}
              <code>VITE_API_URL</code> in <code>.env</code>.
            </p>
          ) : null}
          {onRetry ? (
            <button type="button" className="btn btn-secondary" onClick={onRetry}>
              <RefreshCw size={16} /> Retry
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
