import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Boxes, Gauge, IndianRupee, Scale, Timer, Warehouse } from "lucide-react";
import { api } from "../api/client";
import { ChartCard } from "../components/ChartCard";
import { PageHeader, SegmentedControl } from "../components/Controls";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { ProductDetailDrawer } from "../components/ProductDetailDrawer";
import { SkeletonCard } from "../components/Skeleton";
import type {
  AbcCell,
  AbcProduct,
  AnalyticsFilters,
  AnalyticsMonth,
  AnalyticsOverview,
  MovementReport,
  ProductDetail,
  RankedProduct,
  SlowItem,
  SupplierScore,
} from "../types/api";
import {
  analyticsFetchKey,
  clearAnalyticsQuery,
  readAnalyticsQuery,
  writeAnalyticsQuery,
  type AnalyticsQuery,
} from "../utils/analyticsQuery";
import { formatNumber, formatPaise } from "../utils/format";

type Bundle = {
  overview: AnalyticsOverview;
  months: AnalyticsMonth[];
  turnover: AnalyticsMonth[];
  turnoverDefinition?: string;
  movements: MovementReport;
  byValue: RankedProduct[];
  byQuantity: RankedProduct[];
  sales: AnalyticsMonth[];
  categories: { category: string; inventory_value_paise: number; revenue_paise: number; value_share?: number | null; sku_count: number }[];
  cells: AbcCell[];
  abcProducts: AbcProduct[];
  abcRule?: string;
  xyzRule?: string;
  slow: SlowItem[];
  slowDefinition?: string;
  suppliers: SupplierScore[];
  supplierNote?: string;
  catalogNote?: string;
  filters: AnalyticsFilters;
};

export function InventoryAnalytics() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const query = useMemo(() => readAnalyticsQuery(params), [params]);
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [drawerId, setDrawerId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchKey = analyticsFetchKey(query);

  useEffect(() => {
    const ac = new AbortController();
    let active = true;
    setLoading(true);
    const q = {
      date_from: query.from,
      date_to: query.to,
      year: query.year,
      month: query.month,
      category: query.category,
      supplier_id: query.supplier,
      product_id: query.product,
    };
    Promise.all([
      api.analyticsOverview(q, ac.signal),
      api.analyticsTrend(q, ac.signal),
      api.analyticsTurnover(q, ac.signal),
      api.analyticsMovements(q, ac.signal),
      api.analyticsTop(q, ac.signal),
      api.analyticsSales(q, ac.signal),
      api.analyticsCategories(q, ac.signal),
      api.analyticsAbc({ ...q, page_size: 200 }, ac.signal),
      api.analyticsSlow({ ...q, page_size: 50 }, ac.signal),
      api.analyticsSuppliers(q, ac.signal),
      api.analyticsFilters(ac.signal),
    ])
      .then(([overview, trend, turnover, movements, top, sales, categories, abc, slow, suppliers, filters]) => {
        if (!active) return;
        setBundle({
          overview,
          months: trend.months ?? [],
          turnover: turnover.months ?? [],
          turnoverDefinition: turnover.definition,
          movements,
          byValue: top.by_value ?? [],
          byQuantity: top.by_quantity ?? [],
          sales: sales.months ?? [],
          categories: categories.categories ?? [],
          cells: abc.cells ?? [],
          abcProducts: abc.products ?? [],
          abcRule: abc.abc_rule,
          xyzRule: abc.xyz_rule,
          slow: slow.items ?? [],
          slowDefinition: slow.definition,
          suppliers: suppliers.items ?? [],
          supplierNote: suppliers.simulated_label,
          catalogNote: suppliers.catalog_reliability_label,
          filters,
        });
        setError(null);
        setOffline(false);
      })
      .catch((err: unknown) => {
        if (!active || ac.signal.aborted) return;
        setOffline(err instanceof TypeError);
        setError(err instanceof Error ? err.message : "Analytics request failed");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      ac.abort();
    };
  }, [fetchKey, query]);

  useEffect(() => {
    if (drawerId == null) {
      setDetail(null);
      return;
    }
    const ac = new AbortController();
    setDetailLoading(true);
    api
      .productDetail(drawerId, ac.signal)
      .then((product) => {
        setDetail(product);
        setDetailLoading(false);
      })
      .catch(() => {
        if (!ac.signal.aborted) setDetailLoading(false);
      });
    return () => ac.abort();
  }, [drawerId]);

  function update(partial: Partial<AnalyticsQuery>) {
    const next = { ...query, ...partial };
    setParams(writeAnalyticsQuery(next), { replace: true });
  }

  const ranked = query.rank === "quantity" ? bundle?.byQuantity ?? [] : bundle?.byValue ?? [];
  const selectedMonth =
    query.year && query.month ? `${query.year}-${String(query.month).padStart(2, "0")}` : "";
  const cellProducts = query.cell
    ? (bundle?.abcProducts ?? []).filter((row) => row.cell === query.cell)
    : bundle?.abcProducts ?? [];

  if (loading && !bundle) {
    return (
      <>
        <PageHeader title="Inventory Analytics" subtitle="Loading historical inventory intelligence…" />
        <div className="grid-kpi-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </>
    );
  }
  if (error && !bundle) return <ErrorState message={error} onRetry={() => setParams(params)} offline={offline} />;

  const overview = bundle?.overview;
  const filters = bundle?.filters;
  const period =
    overview?.period_start && overview.period_end
      ? `${overview.period_start} to ${overview.period_end}`
      : "No snapshot days in this filter";

  return (
    <>
      <PageHeader
        title="Inventory Analytics"
        subtitle="Historical inventory value, turnover, and movement. Reconstructed receipts are labeled synthetic. Live stock stays separate from those snapshots."
        actions={<span className="badge badge-muted">{period}</span>}
      />

      <FilterBar query={query} filters={filters} onChange={update} onClear={() => setParams(writeAnalyticsQuery(clearAnalyticsQuery()), { replace: true })} />

      {!overview?.ready ? (
        <EmptyState
          title="Analytics history is not built"
          message={overview?.note || "Run python -m app.cli build-analytics --seed 42"}
        />
      ) : (
        <>
          <div className="grid-kpi-6">
            <KpiCard
              label="Inventory value"
              icon={<IndianRupee size={16} />}
              value={formatPaise(overview.inventory_value_paise)}
              sublabel={`Period-end cost. Live on-hand ${formatPaise(overview.live_inventory_value_paise)}`}
            />
            <KpiCard
              label="Stock available"
              icon={<Boxes size={16} />}
              value={formatNumber(overview.stock_units)}
              sublabel={`Period-end units. Live ${formatNumber(overview.live_stock_units)}`}
            />
            <article className="card kpi-card">
              <div className="kpi-top">
                <div className="kpi-label">Inventory turnover</div>
                <span className="kpi-icon"><Gauge size={16} /></span>
              </div>
              <div className="gauge-row">
                <TurnoverGauge value={overview.turnover ?? null} target={overview.turnover_reference_target ?? 6} />
                <div>
                  <div className="kpi-value tabular">{overview.turnover == null ? "N/A" : overview.turnover.toFixed(2)}</div>
                  <p className="note">Reference target {overview.turnover_reference_target ?? 6} is a demo planning mark, not a benchmark.</p>
                </div>
              </div>
            </article>
            <KpiCard
              label="Inventory to sales"
              icon={<Scale size={16} />}
              value={overview.inventory_to_sales == null ? "N/A" : overview.inventory_to_sales.toFixed(2)}
              sublabel="Period-end value / fulfilled revenue"
            />
            <KpiCard
              label="Days inventory outstanding"
              icon={<Timer size={16} />}
              value={overview.days_inventory_outstanding == null ? "N/A" : overview.days_inventory_outstanding.toFixed(1)}
              sublabel="Accounting DIO, not forecast cover"
            />
            <KpiCard
              label="Excess inventory value"
              icon={<Warehouse size={16} />}
              tone="warn"
              value={overview.excess_inventory_value_paise == null ? "N/A" : formatPaise(overview.excess_inventory_value_paise)}
              sublabel="Current proxy. The date filter does not change it."
            />
          </div>

          <div className="analytics-split">
            <ChartCard
              title="Inventory value over time"
              subtitle="Month-end purchasing-cost value from reconstructed snapshots."
              ariaLabel="Monthly inventory value"
            >
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={bundle?.months ?? []} onClick={(state) => pickMonth(state, update)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={56} tickFormatter={(v) => compactPaise(Number(v))} />
                  <Tooltip content={<MonthTip />} />
                  <Bar dataKey="inventory_value_paise" name="Inventory value" radius={[6, 6, 0, 0]}>
                    {(bundle?.months ?? []).map((row) => (
                      <Cell key={row.month} fill={row.month === selectedMonth ? "var(--color-forecast)" : "var(--color-primary)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="chip-row" aria-label="Select a month">
                {(bundle?.months ?? []).map((row) => (
                  <button
                    key={row.month}
                    type="button"
                    className="chip"
                    aria-pressed={row.month === selectedMonth}
                    onClick={() => selectMonth(row.month, update)}
                  >
                    {row.month}
                  </button>
                ))}
              </div>
            </ChartCard>
            <ChartCard title="Monthly turnover" subtitle={bundle?.turnoverDefinition || "Month COGS / average inventory. Not annualized."}>
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={bundle?.turnover ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={40} />
                  <Tooltip content={<TurnoverTip />} />
                  <Line dataKey="turnover" name="Turns" stroke="var(--color-forecast)" strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <div className="analytics-split">
            <ChartCard
              title="Top 10 items"
              subtitle="Period-end inventory. Select a product to open its intelligence drawer."
              actions={
                <SegmentedControl<"value" | "quantity">
                  label="Ranking measure"
                  value={query.rank}
                  onChange={(rank) => update({ rank })}
                  options={[
                    { id: "value", label: "Value" },
                    { id: "quantity", label: "Quantity" },
                  ]}
                />
              }
            >
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={ranked} layout="vertical" margin={{ left: 8, right: 12 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis type="number" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} tickFormatter={(v) => (query.rank === "value" ? compactPaise(Number(v)) : formatNumber(Number(v)))} />
                  <YAxis type="category" dataKey="sku" width={84} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                  <Tooltip content={<RankTip mode={query.rank} />} />
                  <Bar
                    dataKey={query.rank === "value" ? "inventory_value_paise" : "stock_units"}
                    fill="var(--color-primary)"
                    radius={[0, 6, 6, 0]}
                    onClick={(row: RankedProduct) => setDrawerId(row.product_id)}
                  />
                </BarChart>
              </ResponsiveContainer>
              <ol className="rank-list">
                {ranked.map((row) => (
                  <li key={row.product_id}>
                    <button type="button" onClick={() => setDrawerId(row.product_id)}>
                      <span className="rank-index">{row.rank}</span>
                      <span>
                        <strong>{row.name}</strong>
                        <span className="note">{row.sku} · {row.category}</span>
                      </span>
                      <span className="tabular">
                        {query.rank === "value" ? formatPaise(row.inventory_value_paise) : `${formatNumber(row.stock_units)} units`}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            </ChartCard>
            <ChartCard
              title="Inventory movements"
              subtitle={bundle?.movements.formula || "Unit waterfall for the selected window."}
            >
              {bundle?.movements.opening_units == null ? (
                <EmptyState title="No movements" message="The selected window has no snapshots." />
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={waterfallSteps(bundle.movements)}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} interval={0} />
                      <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={48} />
                      <Tooltip content={<WaterfallTip />} />
                      <Bar dataKey="base" stackId="flow" fill="transparent" />
                      <Bar dataKey="span" stackId="flow" radius={[4, 4, 0, 0]}>
                        {waterfallSteps(bundle.movements).map((step) => (
                          <Cell
                            key={step.name}
                            fill={step.kind === "down" ? "var(--color-risk)" : step.kind === "up" ? "var(--color-forecast)" : "var(--color-primary)"}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <p className="note">
                    Units conserved: {bundle.movements.conserved_units ? "yes" : "no"}. Value conserved:{" "}
                    {bundle.movements.conserved_value ? "yes" : "no"}. Closing value {formatPaise(bundle.movements.closing_value_paise)}.
                  </p>
                </>
              )}
            </ChartCard>
          </div>

          <div className="analytics-split">
            <ChartCard title="Inventory and sales" subtitle="Bars use rupees. The line is the inventory-to-sales ratio.">
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={bundle?.sales ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                  <YAxis yAxisId="money" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={56} tickFormatter={(v) => compactPaise(Number(v))} />
                  <YAxis yAxisId="ratio" orientation="right" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={36} />
                  <Tooltip content={<SalesTip />} />
                  <Legend />
                  <Bar yAxisId="money" dataKey="inventory_value_paise" name="Inventory value" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="money" dataKey="revenue_paise" name="Fulfilled revenue" fill="var(--color-forecast)" radius={[4, 4, 0, 0]} />
                  <Line yAxisId="ratio" dataKey="inventory_to_sales" name="Ratio" stroke="var(--color-warning)" strokeWidth={2} dot={false} connectNulls={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </ChartCard>
            <ChartCard title="Category contribution" subtitle="Period-end inventory value. Select a category to filter the page.">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart
                  data={bundle?.categories ?? []}
                  layout="vertical"
                  margin={{ left: 8, right: 8 }}
                  onClick={(state) => {
                    const category = state?.activePayload?.[0]?.payload?.category as string | undefined;
                    if (category) update({ category });
                  }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis type="number" tickFormatter={(v) => compactPaise(Number(v))} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                  <YAxis type="category" dataKey="category" width={110} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
                  <Tooltip formatter={(value) => formatPaise(typeof value === "number" ? value : null)} />
                  <Bar dataKey="inventory_value_paise" name="Inventory value" radius={[0, 6, 6, 0]}>
                    {(bundle?.categories ?? []).map((row) => (
                      <Cell key={row.category} fill={row.category === query.category ? "var(--color-forecast)" : "var(--color-primary)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <section className="card" style={{ marginBottom: 16 }}>
            <h2 className="card-title">Insight summary</h2>
            <p className="card-sub">Deterministic statements from the filtered calculations.</p>
            <ul className="insight-list">
              {(overview.insights ?? []).map((insight) => (
                <li key={insight.id}>{insight.text}</li>
              ))}
            </ul>
            {overview.reconciliation_note ? <p className="note">{overview.reconciliation_note}</p> : null}
            {overview.cost_model ? <p className="note">{overview.cost_model}</p> : null}
          </section>

          <section className="card" style={{ marginBottom: 16 }}>
            <h2 className="card-title">ABC–XYZ segmentation</h2>
            <p className="card-sub">{bundle?.abcRule}</p>
            <p className="card-sub">{bundle?.xyzRule}</p>
            <div className="abc-grid" role="grid" aria-label="ABC XYZ matrix">
              <span />
              {["X", "Y", "Z"].map((xyz) => (
                <strong key={xyz} className="abc-head">{xyz}</strong>
              ))}
              {["A", "B", "C"].map((abc) => (
                <AbcRow
                  key={abc}
                  abc={abc}
                  cells={bundle?.cells ?? []}
                  selected={query.cell}
                  onSelect={(cell) => update({ cell: query.cell === cell ? undefined : cell })}
                />
              ))}
            </div>
            {query.cell ? (
              <div className="chip-row">
                <span className="chip">{query.cell}: {(bundle?.cells ?? []).find((cell) => cell.cell === query.cell)?.interpretation}</span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => update({ cell: undefined })}>Clear cell</button>
              </div>
            ) : null}
            <DataTable
              rows={cellProducts.slice(0, 12)}
              onSelect={(row) => setDrawerId(row.product_id)}
              columns={[
                { key: "sku", header: "Product", render: (row) => `${row.name} · ${row.sku}` },
                { key: "cell", header: "Cell", render: (row) => row.cell },
                { key: "value", header: "Inventory value", align: "right", render: (row) => formatPaise(row.inventory_value_paise) },
                { key: "revenue", header: "Fulfilled revenue", align: "right", render: (row) => formatPaise(row.revenue_paise) },
              ]}
            />
          </section>

          <section className="card" style={{ marginBottom: 16 }}>
            <h2 className="card-title">Slow-moving and excess stock</h2>
            <p className="card-sub">{bundle?.slowDefinition}</p>
            {bundle?.slow.length ? (
              <DataTable
                rows={bundle.slow}
                onSelect={(row) => setDrawerId(row.product_id)}
                columns={[
                  { key: "product", header: "Product", render: (row) => `${row.name} · ${row.sku}` },
                  { key: "stock", header: "On hand", align: "right", render: (row) => formatNumber(row.stock_units) },
                  { key: "value", header: "Value", align: "right", render: (row) => formatPaise(row.inventory_value_paise) },
                  { key: "sales", header: "Sold 30 / 90", align: "right", render: (row) => `${formatNumber(row.sold_units_30d)} / ${formatNumber(row.sold_units_90d)}` },
                  { key: "cover", header: "Forecast cover", align: "right", render: (row) => (row.forecast_days_of_supply == null ? "N/A" : `${row.forecast_days_of_supply.toFixed(0)} d`) },
                  { key: "action", header: "Suggested action", render: (row) => row.suggested_action },
                ]}
              />
            ) : (
              <EmptyState title="No slow-moving SKUs in this filter" message="The screen found no stock that met the documented rules." />
            )}
          </section>

          <section className="card" style={{ marginBottom: 16 }}>
            <h2 className="card-title">Supplier intelligence</h2>
            <p className="card-sub">{bundle?.catalogNote}</p>
            <p className="card-sub">{bundle?.supplierNote}</p>
            <div className="supplier-grid">
              {(bundle?.suppliers ?? []).map((supplier) => (
                <button
                  key={supplier.supplier_id}
                  type="button"
                  className={`card supplier-card${query.supplier === String(supplier.supplier_id) ? " selected" : ""}`}
                  onClick={() => update({ supplier: String(supplier.supplier_id) })}
                >
                  <strong>{supplier.name}</strong>
                  <span>{supplier.product_count} products · {formatPaise(supplier.stock_value_paise)}</span>
                  <span>Modeled lead time {supplier.modeled_lead_days} days</span>
                  <span>
                    Simulated on time{" "}
                    {supplier.simulated_on_time_rate == null ? "N/A" : `${(supplier.simulated_on_time_rate * 100).toFixed(0)}%`}
                    {" "}({supplier.simulated_receipts} reconstructed receipts)
                  </span>
                  <span>Open reorder qty {formatNumber(supplier.open_reorder_qty)}</span>
                </button>
              ))}
            </div>
          </section>
        </>
      )}

      {(drawerId != null || detailLoading) && (
        <ProductDetailDrawer
          product={detail}
          loading={detailLoading}
          tab="overview"
          onTab={() => undefined}
          onClose={() => setDrawerId(null)}
          onAdjust={() => navigate(`/inventory?product=${drawerId ?? ""}`)}
          onReorder={() => navigate(`/simulator?product=${drawerId ?? ""}`)}
          onExplain={() => {
            const trace = detail?.reorder_recommendation?.trace_id;
            if (trace) navigate(`/agents?trace=${encodeURIComponent(trace)}`);
          }}
        />
      )}
    </>
  );
}

function FilterBar({
  query,
  filters,
  onChange,
  onClear,
}: {
  query: AnalyticsQuery;
  filters?: AnalyticsFilters;
  onChange: (partial: Partial<AnalyticsQuery>) => void;
  onClear: () => void;
}) {
  const chips = [
    query.year ? { key: "year", label: query.year } : null,
    query.month ? { key: "month", label: `Month ${query.month}` } : null,
    query.category ? { key: "category", label: query.category } : null,
    query.supplier ? { key: "supplier", label: filters?.suppliers.find((row) => String(row.id) === query.supplier)?.name ?? "Supplier" } : null,
    query.product ? { key: "product", label: filters?.products.find((row) => String(row.id) === query.product)?.sku ?? "Product" } : null,
    query.cell ? { key: "cell", label: query.cell } : null,
  ].filter(Boolean) as { key: keyof AnalyticsQuery; label: string }[];

  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <div className="filter-bar">
        <select className="select" aria-label="Year" value={query.year ?? ""} onChange={(e) => onChange({ year: e.target.value || undefined })}>
          <option value="">All years</option>
          {(filters?.years ?? []).map((year) => (
            <option key={year} value={year}>{year}</option>
          ))}
        </select>
        <select className="select" aria-label="Month" value={query.month ?? ""} onChange={(e) => onChange({ month: e.target.value || undefined })}>
          <option value="">All months</option>
          {Array.from({ length: 12 }, (_, index) => (
            <option key={index + 1} value={index + 1}>{index + 1}</option>
          ))}
        </select>
        <select className="select" aria-label="Category" value={query.category ?? ""} onChange={(e) => onChange({ category: e.target.value || undefined })}>
          <option value="">All categories</option>
          {(filters?.categories ?? []).map((category) => (
            <option key={category} value={category}>{category}</option>
          ))}
        </select>
        <select className="select" aria-label="Supplier" value={query.supplier ?? ""} onChange={(e) => onChange({ supplier: e.target.value || undefined })}>
          <option value="">All suppliers</option>
          {(filters?.suppliers ?? []).map((supplier) => (
            <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
          ))}
        </select>
        <select className="select" aria-label="Product" value={query.product ?? ""} onChange={(e) => onChange({ product: e.target.value || undefined })}>
          <option value="">All products</option>
          {(filters?.products ?? []).map((product) => (
            <option key={product.id} value={product.id}>{product.sku} · {product.name}</option>
          ))}
        </select>
        <button type="button" className="btn btn-secondary" onClick={onClear}>Clear all</button>
      </div>
      <div className="chip-row">
        {chips.length === 0 ? <span className="note">No active filters. Charts use the full reconstructed history.</span> : null}
        {chips.map((chip) => (
          <button
            key={chip.key}
            type="button"
            className="chip"
            onClick={() => onChange({ [chip.key]: undefined })}
          >
            {chip.label} ×
          </button>
        ))}
      </div>
    </section>
  );
}

function AbcRow({
  abc,
  cells,
  selected,
  onSelect,
}: {
  abc: string;
  cells: AbcCell[];
  selected?: string;
  onSelect: (cell: string) => void;
}) {
  return (
    <>
      <strong className="abc-head">{abc}</strong>
      {["X", "Y", "Z"].map((xyz) => {
        const cell = cells.find((row) => row.cell === `${abc}${xyz}`);
        const key = `${abc}${xyz}`;
        return (
          <button
            key={key}
            type="button"
            className={`abc-cell${selected === key ? " selected" : ""}`}
            aria-pressed={selected === key}
            onClick={() => onSelect(key)}
          >
            <strong>{key}</strong>
            <span>{cell?.sku_count ?? 0} SKUs</span>
            <span>{formatPaise(cell?.inventory_value_paise)}</span>
            <span>{cell?.value_share == null ? "N/A" : `${(cell.value_share * 100).toFixed(1)}%`}</span>
          </button>
        );
      })}
    </>
  );
}

function TurnoverGauge({ value, target }: { value: number | null; target: number }) {
  const max = Math.max(target * 2, 1);
  const pct = value == null ? 0 : Math.max(0, Math.min(1, value / max));
  const length = Math.PI * 40;
  return (
    <svg className="gauge" viewBox="0 0 100 58" role="img" aria-label={value == null ? "Turnover unavailable" : `Turnover ${value.toFixed(2)} compared with reference ${target}`}>
      <path d="M10 50 A40 40 0 0 1 90 50" fill="none" stroke="var(--color-border)" strokeWidth="8" strokeLinecap="round" />
      <path
        d="M10 50 A40 40 0 0 1 90 50"
        fill="none"
        stroke="var(--color-primary)"
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={`${pct * length} ${length}`}
      />
    </svg>
  );
}

function selectMonth(month: string, update: (partial: Partial<AnalyticsQuery>) => void) {
  const [year, mon] = month.split("-");
  update({ year, month: String(Number(mon)), from: undefined, to: undefined });
}

function pickMonth(state: { activeLabel?: string | number } | null, update: (partial: Partial<AnalyticsQuery>) => void) {
  if (state?.activeLabel) selectMonth(String(state.activeLabel), update);
}

function MonthTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: AnalyticsMonth }> }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.month}</strong>
      <div>Inventory value {formatPaise(row.inventory_value_paise)}</div>
      <div>Previous month {row.previous_inventory_value_paise == null ? "N/A" : formatPaise(row.previous_inventory_value_paise)}</div>
      <div>Change {row.absolute_change_paise == null ? "N/A" : formatPaise(row.absolute_change_paise)}</div>
      <div>Percent {row.percent_change == null ? "N/A" : `${row.percent_change.toFixed(1)}%`}</div>
      <div>Fulfilled revenue {formatPaise(row.revenue_paise)}</div>
      <div>Ratio {row.inventory_to_sales == null ? "N/A" : row.inventory_to_sales.toFixed(2)}</div>
    </div>
  );
}

function TurnoverTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: AnalyticsMonth }> }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.month}</strong>
      <div>Turns {row.turnover == null ? "N/A" : row.turnover.toFixed(2)}</div>
      <div>COGS {formatPaise(row.cogs_paise)}</div>
      <div>Average inventory {formatPaise(row.average_inventory_value_paise)}</div>
    </div>
  );
}

function RankTip({ active, payload, mode }: { active?: boolean; payload?: Array<{ payload: RankedProduct }>; mode: "value" | "quantity" }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.name}</strong>
      <div>{row.sku}</div>
      <div>{mode === "value" ? formatPaise(row.inventory_value_paise) : `${formatNumber(row.stock_units)} units`}</div>
    </div>
  );
}

function SalesTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: AnalyticsMonth }> }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.month}</strong>
      <div>Inventory value {formatPaise(row.inventory_value_paise)}</div>
      <div>Fulfilled revenue {formatPaise(row.revenue_paise)}</div>
      <div>Ratio {row.inventory_to_sales == null ? "N/A" : row.inventory_to_sales.toFixed(2)}</div>
    </div>
  );
}

type FlowStep = { name: string; base: number; span: number; amount: number; kind: "total" | "up" | "down" };

function waterfallSteps(report: MovementReport): FlowStep[] {
  let cursor = 0;
  const rows: FlowStep[] = [];
  function total(name: string, value: number) {
    rows.push({ name, base: 0, span: Math.max(value, 0), amount: value, kind: "total" });
    cursor = value;
  }
  function delta(name: string, amount: number) {
    const next = cursor + amount;
    rows.push({ name, base: Math.min(cursor, next), span: Math.abs(amount), amount, kind: amount >= 0 ? "up" : "down" });
    cursor = next;
  }
  total("Opening", report.opening_units ?? 0);
  delta("Receipts", report.receipts_units ?? 0);
  delta("Returns", report.returns_units ?? 0);
  delta("Adjustments", report.adjustments_units ?? 0);
  delta("Sales", -(report.fulfilled_sales_units ?? 0));
  delta("Write-offs", -(report.writeoff_units ?? 0));
  total("Closing", report.closing_units ?? 0);
  return rows;
}

function WaterfallTip({ active, payload }: { active?: boolean; payload?: Array<{ payload: FlowStep }> }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.name}</strong>
      <div>{formatNumber(row.amount)} units</div>
    </div>
  );
}

function compactPaise(paise: number): string {
  const rupees = paise / 100;
  if (Math.abs(rupees) >= 100000) return `₹${(rupees / 100000).toFixed(1)}L`;
  if (Math.abs(rupees) >= 1000) return `₹${(rupees / 1000).toFixed(1)}k`;
  return `₹${Math.round(rupees)}`;
}
