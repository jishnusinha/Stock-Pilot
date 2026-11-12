import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Download, Plus } from "lucide-react";
import { api } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable, type Column } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { ProductDetailDrawer } from "../components/ProductDetailDrawer";
import { RiskBadge } from "../components/Badge";
import { SkeletonCard } from "../components/Skeleton";
import { useDebouncedValue } from "../hooks/useApi";
import type {
  ProductCreateRequest,
  ProductDetail,
  ProductRow,
  ProductUpdateRequest,
  Supplier,
} from "../types/api";
import { formatNumber, formatPaise } from "../utils/format";

const CATEGORIES = [
  "Dairy",
  "Snacks",
  "Beverages",
  "Household",
  "Personal Care",
  "Frozen",
  "General",
];

export function Inventory() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  const page = Number(params.get("page") ?? "1");
  const pageSize = Number(params.get("page_size") ?? "20");
  const searchParam = params.get("search") ?? "";
  const category = params.get("category") ?? "";
  const risk = params.get("risk") ?? "";
  const supplierId = params.get("supplier_id") ?? "";
  const sort = params.get("sort") ?? "name";
  const sortDir = (params.get("dir") ?? "asc") as "asc" | "desc";
  const productId = params.get("product") ? Number(params.get("product")) : null;
  const focusSupplier = params.get("focus") === "supplier";

  const [searchInput, setSearchInput] = useState(searchParam);
  const debouncedSearch = useDebouncedValue(searchInput, 300);

  const [rows, setRows] = useState<ProductRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);

  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [drawerTab, setDrawerTab] = useState<"overview" | "sales" | "history">("overview");
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustDelta, setAdjustDelta] = useState("");
  const [adjustReason, setAdjustReason] = useState("Cycle count adjustment");
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
    api
      .products({
        page,
        page_size: pageSize,
        search: searchParam || undefined,
        category: category || undefined,
        risk: risk || undefined,
        supplier_id: supplierId || undefined,
        sort,
      })
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
  }, [page, pageSize, searchParam, category, risk, supplierId, sort, sortDir]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    api.suppliers().then(setSuppliers).catch(() => setSuppliers([]));
  }, []);

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
    next.set("page", "1");
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

  async function exportCsv() {
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
  }

  async function confirmAdjust() {
    if (!productId) return;
    const delta = Number(adjustDelta);
    if (!Number.isFinite(delta) || !adjustReason.trim()) return;
    await api.adjustStock(productId, { delta, reason: adjustReason });
    setAdjustOpen(false);
    setAdjustDelta("");
    loadProducts();
    const d = await api.productDetail(productId);
    setDetail(d);
  }

  async function saveProduct(payload: ProductCreateRequest | ProductUpdateRequest) {
    setFormBusy(true);
    try {
      if (formMode === "create") {
        const created = await api.createProduct(payload as ProductCreateRequest);
        setFormMode(null);
        loadProducts();
        selectProduct(created.id);
        setDetail(created);
      } else if (formMode === "edit" && productId) {
        const updated = await api.updateProduct(productId, payload as ProductUpdateRequest);
        setFormMode(null);
        loadProducts();
        setDetail(updated);
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
    } finally {
      setFormBusy(false);
    }
  }

  const columns: Column<ProductRow>[] = [
    {
      key: "name",
      header: "Product",
      sortable: true,
      render: (r) => (
        <div>
          <div style={{ fontWeight: 500 }}>{r.name}</div>
          <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{r.sku}</div>
        </div>
      ),
    },
    { key: "category", header: "Category", render: (r) => r.category ?? "—" },
    { key: "supplier", header: "Supplier", render: (r) => r.supplier_name ?? "—" },
    {
      key: "stock",
      header: "Stock",
      align: "right",
      sortable: true,
      render: (r) => formatNumber(r.current_stock),
    },
    {
      key: "dos",
      header: "Days supply",
      align: "right",
      render: (r) => (r.days_of_supply != null ? formatNumber(r.days_of_supply) : "N/A"),
    },
    {
      key: "price",
      header: "Price",
      align: "right",
      render: (r) => formatPaise(r.unit_price_paise),
    },
    {
      key: "risk",
      header: "Risk",
      render: (r) => (r.risk_level ? <RiskBadge level={String(r.risk_level)} /> : "—"),
    },
  ];

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <>
      <header className="page-header">
        <h1>Inventory Explorer</h1>
        <p className="subtitle">
          {total > 0 ? `${formatNumber(total)} SKUs` : "Paginated product catalog"}
          {focusSupplier ? " · Supplier filter focus" : ""}
        </p>
      </header>

      <div className="grid-kpi-4">
        <KpiCard label="Listed SKUs" value={loading ? "…" : formatNumber(total)} />
        <KpiCard label="Page" value={`${page} / ${totalPages}`} />
        <KpiCard label="Page size" value={String(pageSize)} />
        <KpiCard label="Filters active" value={countFilters(category, risk, supplierId, searchParam)} />
      </div>

      <FilterRow>
        <input
          className="input"
          placeholder="Search SKU or name"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          aria-label="Search products"
        />
        <select
          className="select"
          value={category}
          onChange={(e) => setFilter("category", e.target.value)}
          aria-label="Category filter"
        >
          <option value="">All categories</option>
          {[...new Set(rows.map((r) => r.category).filter(Boolean))].map((c) => (
            <option key={c} value={c!}>
              {c}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={risk}
          onChange={(e) => setFilter("risk", e.target.value)}
          aria-label="Risk filter"
        >
          <option value="">All risk levels</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select
          className="select"
          value={supplierId}
          onChange={(e) => setFilter("supplier_id", e.target.value)}
          aria-label="Supplier filter"
        >
          <option value="">All suppliers</option>
          {suppliers.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn-secondary" onClick={() => exportCsv().catch(alert)}>
          <Download size={16} /> Export CSV
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setFormMode("create")}
          disabled={!suppliers.length}
        >
          <Plus size={16} /> Add product
        </button>
      </FilterRow>

      {error && !rows.length ? (
        <ErrorState message={error} onRetry={loadProducts} offline={offline} />
      ) : loading && !rows.length ? (
        <SkeletonCard />
      ) : rows.length === 0 ? (
        <EmptyState title="No products match" message="Try clearing filters or reconnecting to the API." />
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
              if (sort === key) {
                next.set("dir", sortDir === "asc" ? "desc" : "asc");
              } else {
                next.set("sort", key);
                next.set("dir", "asc");
              }
              setParams(next);
            }}
          />
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: 12,
              borderTop: "1px solid var(--color-border)",
            }}
          >
            <span style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
              Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page <= 1}
                onClick={() => setFilter("page", String(page - 1))}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page >= totalPages}
                onClick={() => setFilter("page", String(page + 1))}
              >
                Next
              </button>
            </div>
          </div>
        </section>
      )}

      {(productId != null || detailLoading) && (
        <ProductDetailDrawer
          product={detail}
          loading={detailLoading}
          tab={drawerTab}
          onTab={setDrawerTab}
          onClose={closeDrawer}
          onAdjust={() => setAdjustOpen(true)}
          onReorder={() => navigate(`/simulator?product=${productId}`)}
          onEdit={() => setFormMode("edit")}
          onDelete={() => setDeleteOpen(true)}
        />
      )}

      <ConfirmDialog
        open={adjustOpen}
        title="Adjust stock"
        confirmLabel="Confirm"
        onCancel={() => setAdjustOpen(false)}
        onConfirm={() => confirmAdjust().catch((e) => alert(e.message))}
      >
        <label>
          Quantity change (+/−)
          <input
            className="input"
            type="number"
            value={adjustDelta}
            onChange={(e) => setAdjustDelta(e.target.value)}
            style={{ marginTop: 8 }}
          />
        </label>
        <label style={{ display: "block", marginTop: 12 }}>
          Reason
          <input
            className="input"
            value={adjustReason}
            onChange={(e) => setAdjustReason(e.target.value)}
            style={{ marginTop: 8 }}
          />
        </label>
      </ConfirmDialog>

      <ConfirmDialog
        open={deleteOpen}
        title="Delete product?"
        confirmLabel={formBusy ? "Deleting…" : "Delete"}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => confirmDelete().catch((e) => alert(e.message))}
      >
        <p style={{ margin: 0, fontSize: 14 }}>
          Soft-deletes <strong>{detail?.sku ?? "this SKU"}</strong> from the active catalog.
          Historical sales remain in the database.
        </p>
      </ConfirmDialog>

      {formMode ? (
        <ProductFormDialog
          mode={formMode}
          suppliers={suppliers}
          initial={formMode === "edit" ? detail : null}
          busy={formBusy}
          onCancel={() => setFormMode(null)}
          onSubmit={(payload) => saveProduct(payload).catch((e) => alert(e.message))}
        />
      ) : null}
    </>
  );
}

function countFilters(...parts: string[]) {
  return String(parts.filter(Boolean).length);
}

function FilterRow({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
        gap: 12,
        marginBottom: 16,
        alignItems: "center",
      }}
    >
      {children}
    </div>
  );
}

function ProductFormDialog({
  mode,
  suppliers,
  initial,
  busy,
  onCancel,
  onSubmit,
}: {
  mode: "create" | "edit";
  suppliers: Supplier[];
  initial: ProductDetail | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (payload: ProductCreateRequest | ProductUpdateRequest) => void;
}) {
  const [sku, setSku] = useState(initial?.sku ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [category, setCategory] = useState(initial?.category ?? "General");
  const [supplierId, setSupplierId] = useState(
    String(initial?.supplier?.id ?? suppliers[0]?.id ?? ""),
  );
  const [priceInr, setPriceInr] = useState(
    initial?.unit_price_paise != null ? String(initial.unit_price_paise / 100) : "99",
  );
  const [costInr, setCostInr] = useState(
    initial?.unit_cost_paise != null ? String(initial.unit_cost_paise / 100) : "60",
  );
  const [stock, setStock] = useState(String(initial?.current_stock ?? 0));
  const [pack, setPack] = useState(String(initial?.pack_size ?? 12));

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const price = Math.round(Number(priceInr) * 100);
    const cost = Math.round(Number(costInr) * 100);
    if (!name.trim() || !supplierId || !(price > 0) || cost < 0) {
      alert("Name, supplier, and a positive selling price are required.");
      return;
    }
    if (mode === "create") {
      if (!sku.trim()) {
        alert("SKU is required.");
        return;
      }
      onSubmit({
        sku: sku.trim(),
        name: name.trim(),
        category,
        supplier_id: Number(supplierId),
        unit_cost_paise: cost,
        selling_price_paise: price,
        stock_on_hand: Math.max(0, Math.round(Number(stock) || 0)),
        pack_size: Math.max(1, Math.round(Number(pack) || 12)),
      } satisfies ProductCreateRequest);
    } else {
      onSubmit({
        name: name.trim(),
        category,
        supplier_id: Number(supplierId),
        unit_cost_paise: cost,
        selling_price_paise: price,
        pack_size: Math.max(1, Math.round(Number(pack) || 12)),
      } satisfies ProductUpdateRequest);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={mode === "create" ? "Add product" : "Edit product"}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(27,37,32,0.35)",
        zIndex: 120,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <form
        className="card"
        onSubmit={handleSubmit}
        style={{ width: "min(440px, 100%)", maxHeight: "90vh", overflow: "auto" }}
      >
        <h2 className="card-title">{mode === "create" ? "Add product" : "Edit product"}</h2>
        {mode === "create" ? (
          <Field label="SKU">
            <input className="input" value={sku} onChange={(e) => setSku(e.target.value)} required />
          </Field>
        ) : (
          <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>SKU: {initial?.sku}</p>
        )}
        <Field label="Name">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Category">
          <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Supplier">
          <select className="select" value={supplierId} onChange={(e) => setSupplierId(e.target.value)} required>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="Selling price (₹)">
            <input
              className="input"
              type="number"
              min={0.01}
              step={0.01}
              value={priceInr}
              onChange={(e) => setPriceInr(e.target.value)}
              required
            />
          </Field>
          <Field label="Unit cost (₹)">
            <input
              className="input"
              type="number"
              min={0}
              step={0.01}
              value={costInr}
              onChange={(e) => setCostInr(e.target.value)}
              required
            />
          </Field>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {mode === "create" ? (
            <Field label="Opening stock">
              <input
                className="input"
                type="number"
                min={0}
                value={stock}
                onChange={(e) => setStock(e.target.value)}
              />
            </Field>
          ) : (
            <p style={{ fontSize: 12, color: "var(--color-text-muted)", alignSelf: "end" }}>
              Change stock via Adjust stock
            </p>
          )}
          <Field label="Pack size">
            <input
              className="input"
              type="number"
              min={1}
              value={pack}
              onChange={(e) => setPack(e.target.value)}
            />
          </Field>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "block", marginBottom: 12, fontSize: 13 }}>
      {label}
      <div style={{ marginTop: 6 }}>{children}</div>
    </label>
  );
}
