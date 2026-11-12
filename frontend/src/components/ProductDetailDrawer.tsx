import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ProductDetail } from "../types/api";
import { formatDate } from "../utils/dates";
import { withUncertaintyBand } from "../utils/forecastBand";
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
  onExplain,
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
  onExplain?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!product && !loading) return;
    const root = panelRef.current;
    const closeBtn = root?.querySelector<HTMLElement>("[data-drawer-close]");
    closeBtn?.focus();
    const previous = document.activeElement as HTMLElement | null;

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !root) return;
      const focusables = [...root.querySelectorAll<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")].filter(
        (el) => !el.hasAttribute("disabled"),
      );
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [product, loading, onClose]);

  if (!product && !loading) return null;

  return (
    <>
      <button type="button" className="drawer-backdrop" aria-label="Close product details" onClick={onClose} />
      <aside ref={panelRef} className="drawer" role="dialog" aria-modal="true" aria-label="Product details">
        <div className="drawer-head">
          <div>
            {loading ? (
              <Skeleton height={20} width="70%" />
            ) : (
              <>
                <h2 style={{ fontSize: "1.15rem", margin: 0 }}>{product?.name}</h2>
                <div className="note" style={{ marginTop: 2 }}>
                  {product?.sku}
                  {product?.category ? ` · ${product.category}` : ""}
                </div>
                <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {product?.risk_level ? <RiskBadge level={product.risk_level} /> : null}
                  <span className="badge badge-muted">SYNTHETIC_DEMO</span>
                </div>
              </>
            )}
          </div>
          <button type="button" className="icon-btn" data-drawer-close aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <div className="tabs" role="tablist">
          {(
            [
              ["overview", "Overview"],
              ["sales", "Sales & demand"],
              ["history", "History"],
            ] as const
          ).map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => onTab(id)}>
              {label}
            </button>
          ))}
        </div>
        <div className="drawer-body">
          {loading || !product ? (
            <Skeleton height={220} />
          ) : tab === "overview" ? (
            <Overview product={product} onAdjust={onAdjust} onReorder={onReorder} onExplain={onExplain} onEdit={onEdit} onDelete={onDelete} />
          ) : tab === "sales" ? (
            <SalesTab product={product} />
          ) : (
            <HistoryTab product={product} />
          )}
        </div>
      </aside>
    </>
  );
}

function Overview({
  product,
  onAdjust,
  onReorder,
  onExplain,
  onEdit,
  onDelete,
}: {
  product: ProductDetail;
  onAdjust: () => void;
  onReorder: () => void;
  onExplain?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  return (
    <>
      <div className="stat-grid">
        <Tile label="On hand" value={formatNumber(product.current_stock)} />
        <Tile label="Days of supply" value={product.days_of_supply != null ? formatNumber(Math.round(product.days_of_supply)) : "N/A"} />
        <Tile label="Selling price" value={formatPaise(product.unit_price_paise)} />
        <Tile label="Unit cost" value={formatPaise(product.unit_cost_paise)} />
        <Tile label="Supplier" value={product.supplier?.name ?? "N/A"} />
        <Tile
          label="Lead time"
          value={product.supplier?.lead_time_days != null ? `${product.supplier.lead_time_days} days` : "N/A"}
        />
      </div>
      {product.reorder_recommendation ? (
        <div className="card rec-panel" style={{ marginTop: 14, padding: 12 }}>
          <strong>Reorder recommendation</strong>
          <p className="note">{product.reorder_recommendation.rationale || "Open recommendation from the optimizer."}</p>
          <p className="tabular" style={{ fontWeight: 650 }}>
            Suggested quantity: {formatNumber(product.reorder_recommendation.suggested_qty)}
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button type="button" className="btn btn-primary" onClick={onReorder}>
              Simulate decision
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!product.reorder_recommendation.trace_id}
              title={product.reorder_recommendation.trace_id ? "Open the stored agent trace" : "No execution trace is stored for this recommendation"}
              onClick={onExplain}
            >
              Explain recommendation
            </button>
          </div>
        </div>
      ) : (
        <p className="note">No open reorder recommendation for this SKU.</p>
      )}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 }}>
        <button type="button" className="btn btn-secondary" onClick={onAdjust}>
          Adjust stock
        </button>
        {onEdit ? (
          <button type="button" className="btn btn-secondary" onClick={onEdit}>
            Edit
          </button>
        ) : null}
        {!product.reorder_recommendation ? (
          <button type="button" className="btn btn-primary" onClick={onReorder}>
            What-if reorder
          </button>
        ) : null}
        {onDelete ? (
          <button type="button" className="btn btn-secondary" onClick={onDelete} style={{ color: "var(--color-risk)" }}>
            Remove
          </button>
        ) : null}
      </div>
    </>
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

function SalesTab({ product }: { product: ProductDetail }) {
  const history = (product.sales_history ?? []).map((s) => ({
    date: s.date,
    actual: s.units,
    is_forecast: false as const,
  }));
  const forecast = withUncertaintyBand(product.forecast ?? []);
  const combined = [...history, ...forecast];
  return (
    <>
      <p className="note" style={{ marginTop: 0 }}>
        Recent sales and the stored 28-day forecast. The shaded area is p90 − p10, drawn once.
      </p>
      {combined.length === 0 ? (
        <p className="note">No sales or forecast series for this SKU.</p>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={combined}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => formatDate(String(d)).slice(0, 6)} minTickGap={20} />
            <YAxis tick={{ fontSize: 10 }} width={36} />
            <Tooltip labelFormatter={(l) => formatDate(String(l))} />
            <Area dataKey="bandBase" stackId="b" stroke="none" fill="transparent" legendType="none" />
            <Area dataKey="bandSpan" stackId="b" stroke="none" fill="rgba(37,99,235,0.18)" name="p10–p90" />
            <Line dataKey="actual" stroke="var(--color-primary)" dot={false} name="Actual" connectNulls={false} />
            <Line dataKey="p50" stroke="var(--color-forecast)" strokeDasharray="4 3" dot={false} name="Forecast p50" connectNulls={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </>
  );
}

function HistoryTab({ product }: { product: ProductDetail }) {
  const moves = product.movements ?? [];
  if (!moves.length) return <p className="note">No stock movements recorded.</p>;
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, fontSize: 13 }}>
      {moves.map((m) => (
        <li key={m.id} style={{ padding: "10px 0", borderBottom: "1px solid var(--color-border)", display: "flex", justifyContent: "space-between", gap: 8 }}>
          <span>
            {new Date(m.created_at).toLocaleString("en-IN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
            <div className="note" style={{ margin: 0 }}>{m.reason}</div>
          </span>
          <span className="tabular" style={{ color: m.delta >= 0 ? "var(--color-primary)" : "var(--color-risk)", fontWeight: 650 }}>
            {m.delta >= 0 ? "+" : ""}
            {m.delta}
          </span>
        </li>
      ))}
    </ul>
  );
}
