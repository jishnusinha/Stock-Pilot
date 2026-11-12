import { X } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ProductDetail } from "../types/api";
import { formatDate } from "../utils/dates";
import { formatNumber, formatPaise } from "../utils/format";
import { RiskBadge } from "./Badge";
import { Skeleton } from "./Skeleton";

type Tab = "overview" | "sales" | "history";

export function ProductDetailDrawer({
  product,
  loading,
  tab,
  onTab,
  onClose,
  onAdjust,
  onReorder,
  onEdit,
  onDelete,
}: {
  product: ProductDetail | null;
  loading: boolean;
  tab: Tab;
  onTab: (t: Tab) => void;
  onClose: () => void;
  onAdjust: () => void;
  onReorder: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  if (!product && !loading) return null;

  return (
    <aside
      role="dialog"
      aria-label="Product details"
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: "min(420px, 100vw)",
        height: "100vh",
        background: "var(--color-card)",
        borderLeft: "1px solid var(--color-border)",
        boxShadow: "-4px 0 24px rgba(0,0,0,0.08)",
        zIndex: 100,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <header
        style={{
          padding: 16,
          borderBottom: "1px solid var(--color-border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          {loading ? (
            <Skeleton height={20} width="70%" />
          ) : (
            <>
              <h2 style={{ fontSize: 1.1 + "rem", margin: 0 }}>{product?.name}</h2>
              <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{product?.sku}</span>
            </>
          )}
        </div>
        <button type="button" className="btn btn-secondary" aria-label="Close" onClick={onClose} style={{ padding: 8 }}>
          <X size={18} />
        </button>
      </header>
      <TabRow tab={tab} onTab={onTab} />
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {loading ? (
          <Skeleton height={200} />
        ) : product ? (
          <>
            {tab === "overview" && (
              <Overview
                product={product}
                onAdjust={onAdjust}
                onReorder={onReorder}
                onEdit={onEdit}
                onDelete={onDelete}
              />
            )}
            {tab === "sales" && <SalesTab product={product} />}
            {tab === "history" && <HistoryTab product={product} />}
          </>
        ) : null}
      </div>
    </aside>
  );
}

function TabRow({ tab, onTab }: { tab: Tab; onTab: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "sales", label: "Sales & Demand" },
    { id: "history", label: "History" },
  ];
  return (
    <div style={{ display: "flex", borderBottom: "1px solid var(--color-border)" }} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={tab === t.id}
          onClick={() => onTab(t.id)}
          style={{
            flex: 1,
            padding: "12px 8px",
            border: "none",
            background: tab === t.id ? "var(--color-mint)" : "transparent",
            borderBottom: tab === t.id ? "2px solid var(--color-primary)" : "2px solid transparent",
            cursor: "pointer",
            fontWeight: tab === t.id ? 600 : 400,
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function Overview({
  product,
  onAdjust,
  onReorder,
  onEdit,
  onDelete,
}: {
  product: ProductDetail;
  onAdjust: () => void;
  onReorder: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  return (
    <>
      <dl style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 13 }}>
        <dt style={{ color: "var(--color-text-muted)" }}>Stock</dt>
        <dd className="tabular" style={{ margin: 0 }}>{formatNumber(product.current_stock)}</dd>
        <dt style={{ color: "var(--color-text-muted)" }}>Days of supply</dt>
        <dd className="tabular" style={{ margin: 0 }}>
          {product.days_of_supply != null ? formatNumber(product.days_of_supply) : "N/A"}
        </dd>
        <dt style={{ color: "var(--color-text-muted)" }}>Price</dt>
        <dd style={{ margin: 0 }}>{formatPaise(product.unit_price_paise)}</dd>
        <dt style={{ color: "var(--color-text-muted)" }}>Cost</dt>
        <dd style={{ margin: 0 }}>{formatPaise(product.unit_cost_paise)}</dd>
        <dt style={{ color: "var(--color-text-muted)" }}>Risk</dt>
        <dd style={{ margin: 0 }}>
          {product.risk_level ? <RiskBadge level={product.risk_level} /> : "N/A"}
        </dd>
        <dt style={{ color: "var(--color-text-muted)" }}>Category</dt>
        <dd style={{ margin: 0 }}>{product.category ?? "N/A"}</dd>
        <dt style={{ color: "var(--color-text-muted)" }}>Supplier</dt>
        <dd style={{ margin: 0 }}>{product.supplier?.name ?? "N/A"}</dd>
        <dt style={{ color: "var(--color-text-muted)" }}>Lead time</dt>
        <dd style={{ margin: 0 }}>
          {product.supplier?.lead_time_days != null
            ? `${product.supplier.lead_time_days} days`
            : "N/A"}
        </dd>
      </dl>
      {product.reorder_recommendation ? (
        <div className="card" style={{ marginTop: 16, padding: 12, background: "var(--color-mint)" }}>
          <strong>ML recommendation</strong>
          <p style={{ fontSize: 13 }}>{product.reorder_recommendation.rationale}</p>
          <p className="tabular">
            Suggested qty: {formatNumber(product.reorder_recommendation.suggested_qty)}
          </p>
        </div>
      ) : null}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
        <button type="button" className="btn btn-secondary" onClick={onAdjust}>
          Adjust stock
        </button>
        {onEdit ? (
          <button type="button" className="btn btn-secondary" onClick={onEdit}>
            Edit product
          </button>
        ) : null}
        <button type="button" className="btn btn-primary" onClick={onReorder}>
          Review reorder
        </button>
        {onDelete ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onDelete}
            style={{ color: "var(--color-risk)" }}
          >
            Delete
          </button>
        ) : null}
      </div>
    </>
  );
}

function SalesTab({ product }: { product: ProductDetail }) {
  const sales = product.sales_history ?? [];
  const forecast = product.forecast ?? [];
  const combined = [
    ...sales.map((s) => ({ date: s.date, actual: s.units, type: "hist" })),
    ...forecast.map((f) => ({
      date: f.date,
      p50: f.p50,
      p10: f.p10,
      p90: f.p90,
      type: "fc",
    })),
  ].slice(-90);

  return (
    <>
      <p style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
        Historical sales (~30d) and 28-day forecast (p10–p90 nominal 80% interval)
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={combined} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => formatDate(d).slice(0, 6)} />
          <YAxis tick={{ fontSize: 10 }} width={40} />
          <Tooltip labelFormatter={(l) => formatDate(String(l))} />
          <Line type="monotone" dataKey="actual" stroke="var(--color-primary)" dot={false} name="Actual" />
          <Line type="monotone" dataKey="p50" stroke="var(--color-forecast)" strokeDasharray="4 4" dot={false} name="Forecast p50" />
        </LineChart>
      </ResponsiveContainer>
    </>
  );
}

function HistoryTab({ product }: { product: ProductDetail }) {
  const moves = product.movements ?? [];
  if (!moves.length) {
    return <p style={{ color: "var(--color-text-muted)" }}>No stock movements recorded.</p>;
  }
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, fontSize: 13 }}>
      {moves.map((m) => (
        <li
          key={m.id}
          style={{
            padding: "10px 0",
            borderBottom: "1px solid var(--color-border)",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          <span>
            {formatDateTime(m.created_at)} — {m.reason}
          </span>
          <span className="tabular" style={{ color: m.delta >= 0 ? "var(--color-primary)" : "var(--color-risk)" }}>
            {m.delta >= 0 ? "+" : ""}
            {m.delta}
          </span>
        </li>
      ))}
    </ul>
  );
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("en-IN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
