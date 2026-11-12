import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { StatusBadge } from "../components/Badge";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { PageHeader, SegmentedControl } from "../components/Controls";
import { SkeletonCard } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import type { CalendarItem, ReorderRow } from "../types/api";
import { formatDateTime } from "../utils/dates";
import { formatNumber, formatPaise } from "../utils/format";

type Tab = "all" | "pending" | "approved" | "received" | "rejected";
type Action = "approve" | "reject" | "receive";

export function Reorders() {
  const toast = useToast();
  const navigate = useNavigate();
  const [rows, setRows] = useState<ReorderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [tab, setTab] = useState<Tab>("all");
  const [selected, setSelected] = useState<ReorderRow | null>(null);
  const [pendingAction, setPendingAction] = useState<{ row: ReorderRow; action: Action } | null>(null);
  const [acting, setActing] = useState(false);
  const [calendar, setCalendar] = useState<CalendarItem[]>([]);
  const [calendarNote, setCalendarNote] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api
      .reorders()
      .then((r) => {
        setRows(r);
        setOffline(false);
        setError(null);
        setSelected((current) => (current ? r.find((row) => row.id === current.id) ?? null : null));
      })
      .catch((e: Error) => {
        setError(e.message);
        setOffline(e.name === "TypeError");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    api
      .reorderCalendar()
      .then((payload) => {
        setCalendar(payload.items);
        setCalendarNote(payload.note);
      })
      .catch(() => {
        setCalendar([]);
        setCalendarNote("The replenishment calendar could not be loaded.");
      });
  }, [load]);

  const counts = useMemo(() => countByStatus(rows), [rows]);
  const visible = tab === "all" ? rows : rows.filter((r) => r.status.toLowerCase() === tab);

  async function confirmAction() {
    if (!pendingAction) return;
    setActing(true);
    try {
      const { row, action } = pendingAction;
      if (action === "approve") await api.approveReorder(row.id);
      else if (action === "reject") await api.rejectReorder(row.id);
      else await api.receiveReorder(row.id);
      toast.success(action === "receive" ? "Order received. Stock increased once." : action === "approve" ? "Approved. Physical stock is unchanged." : "Reorder rejected.");
      setPendingAction(null);
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Action failed");
    } finally {
      setActing(false);
    }
  }

  if (loading && !rows.length) {
    return (
      <>
        <PageHeader title="Reorders" subtitle="Loading order workflow…" />
        <SkeletonCard />
      </>
    );
  }
  if (error && !rows.length) return <ErrorState message={error} onRetry={load} offline={offline} />;

  return (
    <>
      <PageHeader
        title="Reorders"
        subtitle="Pending drafts can be approved or rejected. Approving does not order from a supplier and does not change stock. Stock increases once, when an approved order is received."
      />

      <div className="grid-kpi-4">
        <KpiCard label="Pending" value={formatNumber(counts.pending)} sublabel={formatPaise(counts.pendingValue)} />
        <KpiCard label="Approved" value={formatNumber(counts.approved)} sublabel="Waiting to be received" />
        <KpiCard label="Received" value={formatNumber(counts.received)} sublabel={formatPaise(counts.receivedValue)} />
        <KpiCard label="Rejected" tone="risk" value={formatNumber(counts.rejected)} sublabel="Closed without receipt" />
      </div>

      <section className="card" style={{ marginBottom: 16 }}>
        <h2 className="card-title">Replenishment timeline</h2>
        <p className="card-sub">{calendarNote || "Dated items use a stored receipt or a stored prediction. Undated orders have no arrival date."}</p>
        {calendar.length === 0 ? (
          <EmptyState title="No timeline items" message="Recommendations, reorders, and high-risk cover dates will appear here when the API has them." />
        ) : (
          <ol className="timeline">
            {calendar.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="timeline-item"
                  onClick={() => {
                    const match = rows.find((row) => row.product_id === item.product_id);
                    if (match) setSelected(match);
                    else if (item.product_id) navigate(`/inventory?product=${item.product_id}`);
                  }}
                >
                  <strong>{item.date ?? "No date"}</strong>
                  <span className="badge badge-muted">{item.date_role}</span>
                  <span>{item.title}</span>
                  <span className="note">{item.detail}</span>
                  {item.limitation ? <span className="note">{item.limitation}</span> : null}
                </button>
              </li>
            ))}
          </ol>
        )}
      </section>

      <div style={{ marginBottom: 12 }}>
        <SegmentedControl<Tab>
          label="Order status"
          value={tab}
          onChange={setTab}
          options={[
            { id: "all", label: `All ${rows.length}` },
            { id: "pending", label: "Pending" },
            { id: "approved", label: "Approved" },
            { id: "received", label: "Received" },
            { id: "rejected", label: "Rejected" },
          ]}
        />
      </div>

      {visible.length === 0 ? (
        <EmptyState title="No orders in this status" message="Create a draft from Command Center or the simulator." />
      ) : (
        <div className="agents-layout">
          <section className="card" style={{ padding: 0 }}>
            <DataTable
              rows={visible}
              selectedId={selected?.id}
              onSelect={setSelected}
              columns={[
                {
                  key: "product",
                  header: "Product",
                  render: (r) => (
                    <div>
                      <div style={{ fontWeight: 650 }}>{r.product_name ?? `Product #${r.product_id}`}</div>
                      <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{r.sku}</div>
                    </div>
                  ),
                },
                { key: "qty", header: "Qty", align: "right", render: (r) => formatNumber(r.qty) },
                {
                  key: "total",
                  header: "Purchase",
                  align: "right",
                  render: (r) => formatPaise(r.total_paise ?? (r.unit_cost_paise ?? 0) * r.qty),
                },
                { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
                { key: "created", header: "Created", render: (r) => formatDateTime(r.created_at) },
              ]}
            />
          </section>
          <OrderDrawer row={selected} onAct={(row, action) => setPendingAction({ row, action })} />
        </div>
      )}

      <ConfirmDialog
        open={pendingAction != null}
        title={pendingAction ? titleFor(pendingAction.action) : ""}
        confirmLabel={acting ? "Working…" : pendingAction ? labelFor(pendingAction.action) : "Confirm"}
        danger={pendingAction?.action === "reject"}
        onCancel={() => setPendingAction(null)}
        onConfirm={() => void confirmAction()}
      >
        <p style={{ margin: 0 }}>
          {pendingAction?.action === "approve"
            ? "Approval records the decision only. On-hand stock stays the same."
            : pendingAction?.action === "receive"
              ? "Receiving posts the quantity to stock exactly once."
              : "Rejection closes the draft. Stock is unchanged."}
        </p>
      </ConfirmDialog>
    </>
  );
}

function OrderDrawer({
  row,
  onAct,
}: {
  row: ReorderRow | null;
  onAct: (row: ReorderRow, action: Action) => void;
}) {
  if (!row) {
    return (
      <section className="card">
        <h2 className="card-title">Order detail</h2>
        <p className="note">Select a row to see the workflow.</p>
      </section>
    );
  }
  const status = row.status.toLowerCase();
  const total = row.total_paise ?? (row.unit_cost_paise ?? 0) * row.qty;
  return (
    <section className="card">
      <h2 className="card-title">{row.product_name ?? `Product #${row.product_id}`}</h2>
      <p className="card-sub">{row.sku} · order #{row.id}</p>
      <div className="stat-grid" style={{ marginTop: 12 }}>
        <Tile label="Quantity" value={formatNumber(row.qty)} />
        <Tile label="Purchase amount" value={formatPaise(total)} />
        <Tile label="Unit cost" value={formatPaise(row.unit_cost_paise)} />
        <Tile label="Status" value={row.status} />
      </div>
      <ol className="note" style={{ paddingLeft: 18 }}>
        <li>Created {formatDateTime(row.created_at)} as a local draft.</li>
        <li>{status === "pending" ? "Waiting for approval. Stock is unchanged." : status === "rejected" ? "Rejected. Stock was not changed." : "Approved. Stock still unchanged."}</li>
        <li>{status === "received" ? "Received. Stock was increased once for this order." : "Not received."}</li>
      </ol>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {status === "pending" ? (
          <>
            <button type="button" className="btn btn-primary" onClick={() => onAct(row, "approve")}>
              Approve
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => onAct(row, "reject")}>
              Reject
            </button>
          </>
        ) : null}
        {status === "approved" ? (
          <button type="button" className="btn btn-primary" onClick={() => onAct(row, "receive")}>
            Mark received
          </button>
        ) : null}
      </div>
    </section>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-tile">
      <div className="lbl">{label}</div>
      <div className="val">{value}</div>
    </div>
  );
}

function countByStatus(rows: ReorderRow[]) {
  const acc = { pending: 0, approved: 0, received: 0, rejected: 0, pendingValue: 0, receivedValue: 0 };
  for (const row of rows) {
    const status = row.status.toLowerCase();
    const total = row.total_paise ?? (row.unit_cost_paise ?? 0) * row.qty;
    if (status === "pending") {
      acc.pending += 1;
      acc.pendingValue += total;
    } else if (status === "approved") acc.approved += 1;
    else if (status === "received") {
      acc.received += 1;
      acc.receivedValue += total;
    } else if (status === "rejected") acc.rejected += 1;
  }
  return acc;
}

function titleFor(action: Action) {
  if (action === "approve") return "Approve this draft?";
  if (action === "reject") return "Reject this draft?";
  return "Receive this order?";
}

function labelFor(action: Action) {
  if (action === "approve") return "Approve";
  if (action === "reject") return "Reject";
  return "Receive";
}
