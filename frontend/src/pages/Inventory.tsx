import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Download, Plus, X } from "lucide-react";
import { api } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable, TablePagination, type Column } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { PageHeader, ProgressBar } from "../components/Controls";
import { ProductDetailDrawer } from "../components/ProductDetailDrawer";
import { RiskBadge } from "../components/Badge";
import { SkeletonCard } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { useDebouncedValue } from "../hooks/useApi";
import type {
  InventorySummary,
  ProductCreateRequest,
  ProductDetail,
  ProductRow,
  ProductUpdateRequest,
  Supplier,
} from "../types/api";
import { productListQuery } from "../utils/productQuery";
import { formatNumber, formatPaise } from "../utils/format";

const FALLBACK_CATEGORIES = ["Beverages", "Dairy", "Frozen", "General", "Household", "Personal Care", "Snacks"];

export function Inventory() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();

  const page = Number(params.get("page") ?? "1");
  const pageSize = Number(params.get("page_size") ?? "20");
  const searchParam = params.get("search") ?? "";
  const category = params.get("category") ?? "";
  const risk = params.get("risk") ?? "";
  const supplierId = params.get("supplier_id") ?? "";
  const stockHealth = params.get("stock_health") ?? "";
  const sort = params.get("sort") ?? "name";
  const sortDir = (params.get("dir") ?? "asc") as "asc" | "desc";
  const productId = params.get("product") ? Number(params.get("product")) : null;

  const [searchInput, setSearchInput] = useState(searchParam);
  const debouncedSearch = useDebouncedValue(searchInput, 300);

  const [rows, setRows] = useState<ProductRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [summary, setSummary] = useState<InventorySummary | null>(null);

  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [drawerTab, setDrawerTab] = useState<"overview" | "sales" | "history">("overview");
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustDelta, setAdjustDelta] = useState("");
  const [adjustReason, setAdjustReason] = useState("Cycle count adjustment");
  const [adjustError, setAdjustError] = useState<string | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [formBusy, setFormBusy] = useState(false);

  useEffect(() => {
    if (debouncedSearch !== searchParam) {
      const next = new URLSearchParams(params);
      if (debouncedSearch) next.set("search", debouncedSearch);
      else next.delete("search");
      next.set("page", "1");
      setParams(next, { replace: true });
    }
  }, [debouncedSearch, searchParam, params, setParams]);

  const loadProducts = useCallback(() => {
    setLoading(true);
    setError(null);
    const query = productListQuery({
      page,
      pageSize,
      search: searchParam,
      category,
      risk,
      supplierId,
      stockHealth,
      sort,
      sortDir,
    });
    api
      .products(query)
      .then((r) => {
        setRows(r.items);
        setTotal(r.total);
        setOffline(false);
      })
      .catch((e: Error) => {
        setError(e.message);
        setOffline(e.name === "TypeError");
      })
      .finally(() => setLoading(false));
  }, [page, pageSize, searchParam, category, risk, supplierId, stockHealth, sort, sortDir]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    api.suppliers().then(setSuppliers).catch(() => setSuppliers([]));
    api.inventorySummary().then(setSummary).catch(() => setSummary(null));
  }, []);

  function refreshSummary() {
    api.inventorySummary().then(setSummary).catch(() => undefined);
  }

  useEffect(() => {
    if (!productId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    api
      .productDetail(productId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, [productId]);

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.set("page", "1");
    setParams(next);
  }

  function selectProduct(id: number) {
    const next = new URLSearchParams(params);
    next.set("product", String(id));
    setParams(next);
  }

  function closeDrawer() {
    const next = new URLSearchParams(params);
    next.delete("product");
    setParams(next);
  }

  function resetFilters() {
    setSearchInput("");
    setParams(new URLSearchParams());
  }

  async function exportCsv() {
    try {
      const blob = await api.exportCsv({
        search: searchParam || undefined,
        category: category || undefined,
        risk: risk || undefined,
        supplier_id: supplierId || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "products.csv";
      a.click();
      URL.revokeObjectURL(url);
      toast.success("CSV export downloaded.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export failed");
    }
  }

  async function confirmAdjust() {
    if (!productId) return;
    const delta = Number(adjustDelta);
    if (!Number.isFinite(delta) || delta === 0) {
      setAdjustError("Enter a non-zero quantity change.");
      return;
    }
    if (!adjustReason.trim()) {
      setAdjustError("A reason is required.");
      return;
    }
    setAdjustError(null);
    await api.adjustStock(productId, { delta, reason: adjustReason.trim() });
    setAdjustOpen(false);
    setAdjustDelta("");
    toast.success("Stock adjusted.");
    loadProducts();
    refreshSummary();
    setDetail(await api.productDetail(productId));
  }

  async function saveProduct(payload: ProductCreateRequest | ProductUpdateRequest) {
    setFormBusy(true);
    try {
      if (formMode === "create") {
        const created = await api.createProduct(payload as ProductCreateRequest);
        setFormMode(null);
        loadProducts();
        refreshSummary();
        selectProduct(created.id);
        setDetail(created);
        toast.success("Product created.");
      } else if (formMode === "edit" && productId) {
        const updated = await api.updateProduct(productId, payload as ProductUpdateRequest);
        setFormMode(null);
        loadProducts();
        setDetail(updated);
        toast.success("Product updated.");
      }
    } finally {
      setFormBusy(false);
    }
  }

  async function confirmDelete() {
    if (!productId) return;
    setFormBusy(true);
    try {
      await api.deleteProduct(productId);
      setDeleteOpen(false);
      closeDrawer();
      loadProducts();
      refreshSummary();
      toast.success("Product removed from the active catalog.");
    } finally {
      setFormBusy(false);
    }
  }

  const categories = summary?.categories?.length ? summary.categories : FALLBACK_CATEGORIES;
  const activeFilters = [
    category ? { key: "category", label: `Category: ${category}` } : null,
    risk ? { key: "risk", label: `Risk: ${risk}` } : null,
    supplierId
      ? { key: "supplier_id", label: `Supplier: ${suppliers.find((s) => String(s.id) === supplierId)?.name ?? supplierId}` }
      : null,
    stockHealth ? { key: "stock_health", label: stockHealth === "low" ? "Low stock" : "Overstocked" } : null,
    searchParam ? { key: "search", label: `Search: ${searchParam}` } : null,
  ].filter(Boolean) as { key: string; label: string }[];

  const columns: Column<ProductRow>[] = [
    {
      key: "name",
      header: "Product",
      sortable: true,
      render: (r) => (
        <div>
          <div style={{ fontWeight: 650 }}>{r.name}</div>
          <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{r.sku}</div>
        </div>
      ),
    },
    { key: "category", header: "Category", sortable: true, render: (r) => r.category ?? "—" },
    { key: "supplier", header: "Supplier", sortable: true, render: (r) => r.supplier_name ?? "—" },
    {
      key: "stock",
      header: "On hand",
      align: "right",
      sortable: true,
      render: (r) => formatNumber(r.current_stock),
    },
    {
      key: "dos",
      header: "Days of supply",
      sortable: true,
      render: (r) => <SupplyMeter days={r.days_of_supply} />,
    },
    {
      key: "price",
      header: "Price",
      align: "right",
      sortable: true,
      render: (r) => formatPaise(r.unit_price_paise),
    },
    {
      key: "forecast",
      header: "Forecast (4 wk)",
      align: "right",
      sortable: true,
      render: (r) => (r.forecast_28d != null ? formatNumber(Math.round(r.forecast_28d)) : "N/A"),
    },
    {
      key: "risk",
      header: "Risk",
      sortable: true,
      render: (r) => (r.risk_level ? <RiskBadge level={String(r.risk_level)} /> : "—"),
    },
  ];

  return (
    <>
      <PageHeader
        title="Inventory Explorer"
        subtitle="Catalog health across every active SKU, not just the current page."
        actions={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => void exportCsv()}>
              <Download size={16} /> Export CSV
            </button>
            <button type="button" className="btn btn-primary" onClick={() => setFormMode("create")} disabled={!suppliers.length}>
              <Plus size={16} /> Add product
            </button>
          </>
        }
      />

      <div className="grid-kpi-4">
        <KpiCard label="Total SKUs" value={summary ? formatNumber(summary.total_skus) : "…"} sublabel="Active catalog" />
        <KpiCard
          label="Low stock"
          tone="risk"
          value={summary ? formatNumber(summary.low_stock) : "…"}
          sublabel="High risk or ≤ 14 days of supply"
          selected={stockHealth === "low"}
          onClick={() => setFilter("stock_health", stockHealth === "low" ? "" : "low")}
        />
        <KpiCard
          label="Overstocked"
          tone="info"
          value={summary ? formatNumber(summary.overstocked) : "…"}
          sublabel="≥ 90 days of supply"
          selected={stockHealth === "overstock"}
          onClick={() => setFilter("stock_health", stockHealth === "overstock" ? "" : "overstock")}
        />
        <KpiCard
          label="Avg days of supply"
          value={summary?.avg_days_of_supply != null ? summary.avg_days_of_supply.toFixed(1) : "N/A"}
          sublabel="Mean across SKUs with a cover estimate"
        />
      </div>

      <div className="filter-bar">
        <input
          className="input"
          placeholder="Search SKU, name, or supplier"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          aria-label="Search products"
        />
        <select className="select" value={category} onChange={(e) => setFilter("category", e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select className="select" value={risk} onChange={(e) => setFilter("risk", e.target.value)} aria-label="Stock risk">
          <option value="">All risk levels</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select className="select" value={supplierId} onChange={(e) => setFilter("supplier_id", e.target.value)} aria-label="Supplier">
          <option value="">All suppliers</option>
          {suppliers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <select
          className="select"
          aria-label="Sort"
          value={`${sort}:${sortDir}`}
          onChange={(e) => {
            const [key, dir] = e.target.value.split(":");
            const next = new URLSearchParams(params);
            next.set("sort", key);
            next.set("dir", dir);
            setParams(next);
          }}
        >
          <option value="name:asc">Name A–Z</option>
          <option value="name:desc">Name Z–A</option>
          <option value="stock:desc">Stock high–low</option>
          <option value="stock:asc">Stock low–high</option>
          <option value="dos:asc">Cover shortest</option>
          <option value="risk:asc">Risk high first</option>
          <option value="price:desc">Price high–low</option>
        </select>
        <button type="button" className="btn btn-secondary" onClick={resetFilters}>
          Reset
        </button>
      </div>

      <div className="chip-row">
        {activeFilters.length === 0 ? <span className="note" style={{ margin: 0 }}>No filters applied · {formatNumber(total)} matching SKUs</span> : null}
        {activeFilters.map((chip) => (
          <span key={chip.key} className="chip">
            {chip.label}
            <button
              type="button"
              aria-label={`Remove ${chip.label}`}
              onClick={() => {
                if (chip.key === "search") setSearchInput("");
                setFilter(chip.key, "");
              }}
            >
              <X size={12} />
            </button>
          </span>
        ))}
      </div>

      {error && !rows.length ? (
        <ErrorState message={error} onRetry={loadProducts} offline={offline} />
      ) : loading && !rows.length ? (
        <div className="grid-kpi-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          title="No products match"
          message="Clear a filter or search for a different SKU."
          action={
            <button type="button" className="btn btn-secondary" onClick={resetFilters}>
              Reset filters
            </button>
          }
        />
      ) : (
        <section className="card" style={{ padding: 0 }}>
          <DataTable
            columns={columns}
            rows={rows}
            selectedId={productId}
            onSelect={(r) => selectProduct(r.id)}
            sortKey={sort}
            sortDir={sortDir}
            onSort={(key) => {
              const next = new URLSearchParams(params);
              if (sort === key) next.set("dir", sortDir === "asc" ? "desc" : "asc");
              else {
                next.set("sort", key);
                next.set("dir", "asc");
              }
              setParams(next);
            }}
          />
          <TablePagination
            page={page}
            pageSize={pageSize}
            total={total}
            onPage={(p) => setFilter("page", String(p))}
            onPageSize={(size) => {
              const next = new URLSearchParams(params);
              next.set("page_size", String(size));
              next.set("page", "1");
              setParams(next);
            }}
          />
        </section>
      )}

      {(productId != null || detailLoading) && (
        <ProductDetailDrawer
          product={detail}
          loading={detailLoading}
          tab={drawerTab}
          onTab={setDrawerTab}
          onClose={closeDrawer}
          onAdjust={() => {
            setAdjustError(null);
            setAdjustOpen(true);
          }}
          onReorder={() => navigate(`/simulator?product=${productId}`)}
          onExplain={() => {
            const trace = detail?.reorder_recommendation?.trace_id;
            if (trace) navigate(`/agents?trace=${encodeURIComponent(trace)}`);
          }}
          onEdit={() => setFormMode("edit")}
          onDelete={() => setDeleteOpen(true)}
        />
      )}

      <ConfirmDialog
        open={adjustOpen}
        title="Adjust stock"
        confirmLabel="Confirm adjustment"
        onCancel={() => setAdjustOpen(false)}
        onConfirm={() => confirmAdjust().catch((e) => toast.error(e instanceof Error ? e.message : "Adjustment failed"))}
      >
        <label className="field">
          Quantity change (+/−)
          <input className="input" type="number" value={adjustDelta} onChange={(e) => setAdjustDelta(e.target.value)} />
        </label>
        <label className="field">
          Reason
          <input className="input" value={adjustReason} onChange={(e) => setAdjustReason(e.target.value)} />
        </label>
        {adjustError ? <p className="field-error">{adjustError}</p> : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={deleteOpen}
        title="Remove product?"
        confirmLabel={formBusy ? "Removing…" : "Remove"}
        danger
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => confirmDelete().catch((e) => toast.error(e instanceof Error ? e.message : "Delete failed"))}
      >
        <p style={{ margin: 0, fontSize: 14 }}>
          Soft-deletes <strong>{detail?.sku ?? "this SKU"}</strong>. Historical sales stay in the database.
        </p>
      </ConfirmDialog>

      {formMode ? (
        <ProductFormDialog
          mode={formMode}
          suppliers={suppliers}
          categories={categories}
          initial={formMode === "edit" ? detail : null}
          busy={formBusy}
          onCancel={() => setFormMode(null)}
          onSubmit={(payload) => saveProduct(payload).catch((e) => toast.error(e instanceof Error ? e.message : "Save failed"))}
        />
      ) : null}
    </>
  );
}

function SupplyMeter({ days }: { days?: number | null }) {
  if (days == null) return <span>N/A</span>;
  const tone = days <= 7 ? "risk" : days <= 14 ? "warn" : days >= 90 ? "info" : "ok";
  return (
    <div style={{ display: "grid", gap: 4, minWidth: 96 }}>
      <span>{formatNumber(Math.round(days))}</span>
      <ProgressBar value={Math.min(100, (days / 45) * 100)} tone={tone} label={`${Math.round(days)} days of supply`} />
    </div>
  );
}

function ProductFormDialog({
  mode,
  suppliers,
  categories,
  initial,
  busy,
  onCancel,
  onSubmit,
}: {
  mode: "create" | "edit";
  suppliers: Supplier[];
  categories: string[];
  initial: ProductDetail | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (payload: ProductCreateRequest | ProductUpdateRequest) => void;
}) {
  const [sku, setSku] = useState(initial?.sku ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [category, setCategory] = useState(initial?.category ?? categories[0] ?? "General");
  const [supplier, setSupplier] = useState(String(initial?.supplier?.id ?? suppliers[0]?.id ?? ""));
  const [priceInr, setPriceInr] = useState(initial?.unit_price_paise != null ? String(initial.unit_price_paise / 100) : "99");
  const [costInr, setCostInr] = useState(initial?.unit_cost_paise != null ? String(initial.unit_cost_paise / 100) : "60");
  const [stock, setStock] = useState(String(initial?.current_stock ?? 0));
  const [pack, setPack] = useState(String(initial?.pack_size ?? 12));
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const price = Math.round(Number(priceInr) * 100);
    const cost = Math.round(Number(costInr) * 100);
    if (!name.trim() || !supplier || !(price > 0) || cost < 0) {
      setFormError("Name, supplier, and a positive selling price are required.");
      return;
    }
    if (mode === "create" && !sku.trim()) {
      setFormError("SKU is required.");
      return;
    }
    setFormError(null);
    if (mode === "create") {
      onSubmit({
        sku: sku.trim(),
        name: name.trim(),
        category,
        supplier_id: Number(supplier),
        unit_cost_paise: cost,
        selling_price_paise: price,
        stock_on_hand: Math.max(0, Math.round(Number(stock) || 0)),
        pack_size: Math.max(1, Math.round(Number(pack) || 12)),
      });
    } else {
      onSubmit({
        name: name.trim(),
        category,
        supplier_id: Number(supplier),
        unit_cost_paise: cost,
        selling_price_paise: price,
        pack_size: Math.max(1, Math.round(Number(pack) || 12)),
      });
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onCancel}>
      <form
        className="card modal-card"
        role="dialog"
        aria-modal="true"
        aria-label={mode === "create" ? "Add product" : "Edit product"}
        onSubmit={handleSubmit}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h2 className="card-title">{mode === "create" ? "Add product" : "Edit product"}</h2>
        {mode === "create" ? (
          <Field label="SKU">
            <input className="input" value={sku} onChange={(e) => setSku(e.target.value)} required />
          </Field>
        ) : (
          <p className="note">SKU: {initial?.sku}</p>
        )}
        <Field label="Name">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Category">
          <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Supplier">
          <select className="select" value={supplier} onChange={(e) => setSupplier(e.target.value)} required>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="Selling price (₹)">
            <input className="input" type="number" min={0.01} step={0.01} value={priceInr} onChange={(e) => setPriceInr(e.target.value)} required />
          </Field>
          <Field label="Unit cost (₹)">
            <input className="input" type="number" min={0} step={0.01} value={costInr} onChange={(e) => setCostInr(e.target.value)} required />
          </Field>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {mode === "create" ? (
            <Field label="Opening stock">
              <input className="input" type="number" min={0} value={stock} onChange={(e) => setStock(e.target.value)} />
            </Field>
          ) : (
            <p className="note">Change stock with Adjust stock.</p>
          )}
          <Field label="Pack size">
            <input className="input" type="number" min={1} value={pack} onChange={(e) => setPack(e.target.value)} />
          </Field>
        </div>
        {formError ? <p className="field-error">{formError}</p> : null}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
          <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "Saving…" : mode === "create" ? "Create" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      {label}
      {children}
    </label>
  );
}
