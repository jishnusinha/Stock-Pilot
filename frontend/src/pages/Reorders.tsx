import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import type { ReorderRow } from "../types/api";
import { formatDateTime } from "../utils/dates";
import { formatNumber, formatPaise } from "../utils/format";

export function Reorders() {
  const [rows, setRows] = useState<ReorderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [acting, setActing] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .reorders()
      .then((r) => {
        setRows(r);
        setOffline(false);
        setError(null);
      })
      .catch((e: Error) => {
        setError(e.message);
        setOffline(e.name === "TypeError");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function act(id: number, action: "approve" | "reject" | "receive") {
    setActing(id);
    try {
      if (action === "approve") await api.approveReorder(id);
      else if (action === "reject") await api.rejectReorder(id);
      else await api.receiveReorder(id);
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActing(null);
    }
  }

  if (loading && !rows.length) return <p>Loading reorders…</p>;
  if (error && !rows.length) return <ErrorState message={error} onRetry={load} offline={offline} />;

  return (
    <>
      <header className="page-header">
        <h1>Reorders</h1>
        <p className="subtitle">
          Draft → approved → received workflow · Approval does not place external supplier orders
        </p>
      </header>

      {rows.length === 0 ? (
        <EmptyState
          title="No reorders"
          message="Create a draft from Command Center or Simulator."
        />
      ) : (
        <section className="card" style={{ padding: 0 }}>
          <DataTable
            rows={rows}
            columns={[
              {
                key: "product",
                header: "Product",
                render: (r) => (
                  <div>
                    <div>{r.product_name ?? `Product #${r.product_id}`}</div>
                    <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{r.sku}</div>
                  </div>
                ),
              },
              {
                key: "qty",
                header: "Qty",
                align: "right",
                render: (r) => formatNumber(r.qty),
              },
              {
                key: "total",
                header: "Total",
                align: "right",
                render: (r) => formatPaise(r.total_paise ?? (r.unit_cost_paise ?? 0) * r.qty),
              },
              {
                key: "status",
                header: "Status",
                render: (r) => <StatusBadge status={r.status} />,
              },
              {
                key: "created",
                header: "Created",
                render: (r) => formatDateTime(r.created_at),
              },
              {
                key: "actions",
                header: "Actions",
                render: (r) => (
                  <ActionButtons row={r} acting={acting} onAct={act} />
                ),
              },
            ]}
          />
        </section>
      )}
    </>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (s === "pending") return <Badge variant="warning">Pending</Badge>;
  if (s === "approved") return <Badge variant="mint">Approved</Badge>;
  if (s === "rejected") return <Badge variant="risk">Rejected</Badge>;
  if (s === "received") return <Badge variant="default">Received</Badge>;
  return <Badge>{status}</Badge>;
}

function ActionButtons({
  row,
  acting,
  onAct,
}: {
  row: ReorderRow;
  acting: number | null;
  onAct: (id: number, action: "approve" | "reject" | "receive") => void;
}) {
  const busy = acting === row.id;
  const s = row.status.toLowerCase();
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {s === "pending" ? (
        <>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onAct(row.id, "approve")}>
            Approve
          </button>
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => onAct(row.id, "reject")}>
            Reject
          </button>
        </>
      ) : null}
      {s === "approved" ? (
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onAct(row.id, "receive")}>
          Receive
        </button>
      ) : null}
    </div>
  );
}
