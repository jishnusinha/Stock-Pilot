import { Boxes, Gauge, IndianRupee, Scale, Timer, Warehouse } from "lucide-react";
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
import { ChartCard } from "../../components/ChartCard";
import { DataTable } from "../../components/DataTable";
import { EmptyState } from "../../components/EmptyState";
import { KpiCard } from "../../components/KpiCard";
import { SegmentedControl } from "../../components/Controls";
import type {
  AbcCell,
  AbcProduct,
  AnalyticsFilters,
  AnalyticsMonth,
  AnalyticsOverview,
  MovementReport,
  RankedProduct,
  SlowItem,
  SupplierScore,
} from "../../types/api";
import type { AnalyticsQuery } from "../../utils/analyticsQuery";
import { formatNumber, formatPaise } from "../../utils/format";
import { HistoricalQualityPanel } from "./HistoricalQualityPanel";
import {
  AbcRow,
  MonthTip,
  RankTip,
  SalesTip,
  TurnoverSpark,
  TurnoverTip,
  WaterfallTip,
  compactPaise,
  monthBarFill,
  monthBarOpacity,
  pickMonth,
  selectMonth,
  waterfallSteps,
} from "./historicalChartHelpers";

export type HistoricalBundle = {
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

export function HistoricalAnalyticsPanel({
  bundle,
  query,
  update,
  onProductSelect,
}: {
  bundle: HistoricalBundle;
  query: AnalyticsQuery;
  update: (partial: Partial<AnalyticsQuery>) => void;
  onProductSelect: (id: number) => void;
}) {
  const overview = bundle.overview;
  const ranked = query.rank === "quantity" ? bundle.byQuantity : bundle.byValue;
  const selectedMonth =
    query.year && query.month ? `${query.year}-${String(query.month).padStart(2, "0")}` : "";
  const cellProducts = query.cell
    ? bundle.abcProducts.filter((row) => row.cell === query.cell)
    : bundle.abcProducts;

  if (!overview.ready) {
    return (
      <EmptyState
        title="Analytics history is not built"
        message={overview.note || "Run python -m app.cli build-analytics --seed 42"}
      />
    );
  }

  return (
    <>
      <div className="grid-kpi-6">
        <KpiCard
          label="Inventory value"
          icon={<IndianRupee size={16} />}
          value={formatPaise(overview.inventory_value_paise)}
          sublabel={`Historical as-of-period, stock on ${overview.period_end ?? "the period end"}. Current operational stock ${formatPaise(overview.live_inventory_value_paise)}`}
        />
        <KpiCard
          label="Stock available"
          icon={<Boxes size={16} />}
          value={formatNumber(overview.stock_units)}
          sublabel={`Historical stock on ${overview.period_end ?? "the period end"}. Current stock ${formatNumber(overview.live_stock_units)}`}
        />
        <article className="card kpi-card">
          <div className="kpi-top">
            <div className="kpi-label">Inventory turnover</div>
            <span className="kpi-icon"><Gauge size={16} /></span>
          </div>
          <div className="gauge-row">
            <TurnoverSpark months={bundle.turnover} />
            <div>
              <div className="kpi-value tabular">{overview.turnover == null ? "N/A" : overview.turnover.toFixed(2)}</div>
              <p className="note">Historical as-of-period. The number is the full ratio. The line is that period's monthly turns, scaled to the data.</p>
            </div>
          </div>
        </article>
        <KpiCard
          label="Inventory to sales"
          icon={<Scale size={16} />}
          value={overview.inventory_to_sales == null ? "N/A" : overview.inventory_to_sales.toFixed(2)}
          sublabel="Historical as-of-period. Period-end value / fulfilled revenue"
        />
        <KpiCard
          label="Days inventory outstanding"
          icon={<Timer size={16} />}
          value={overview.days_inventory_outstanding == null ? "N/A" : overview.days_inventory_outstanding.toFixed(1)}
          sublabel="Historical as-of-period. Accounting DIO, not forecast cover"
        />
        <KpiCard
          label="Excess inventory value"
          icon={<Warehouse size={16} />}
          tone="warn"
          value={overview.excess_inventory_value_paise == null ? "N/A" : formatPaise(overview.excess_inventory_value_paise)}
          sublabel="Current operational state. This forecast overlay was not known in the selected month."
        />
      </div>

      <HistoricalQualityPanel overview={overview} />

      <div className="analytics-split">
        <ChartCard title="Inventory value over time" subtitle="Month-end purchasing-cost value from reconstructed snapshots." ariaLabel="Monthly inventory value">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={bundle.months} onClick={(state) => pickMonth(state, update)}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
              <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={56} tickFormatter={(v) => compactPaise(Number(v))} />
              <Tooltip content={<MonthTip />} />
              <Bar dataKey="inventory_value_paise" name="Inventory value" radius={[6, 6, 0, 0]}>
                {bundle.months.map((row) => (
                  <Cell key={row.month} fill={monthBarFill(row, selectedMonth)} fillOpacity={monthBarOpacity(row)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="chip-row" aria-label="Select a month">
            {bundle.months.map((row) => (
              <button key={row.month} type="button" className="chip" aria-pressed={row.month === selectedMonth} onClick={() => selectMonth(row.month, update)}>
                {row.month}
              </button>
            ))}
          </div>
        </ChartCard>
        <ChartCard title="Monthly turnover" subtitle={bundle.turnoverDefinition || "Month COGS / average inventory. Not annualized."}>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={bundle.turnover}>
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
                onClick={(row: RankedProduct) => onProductSelect(row.product_id)}
              />
            </BarChart>
          </ResponsiveContainer>
          <ol className="rank-list">
            {ranked.map((row) => (
              <li key={row.product_id}>
                <button type="button" onClick={() => onProductSelect(row.product_id)}>
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
        <ChartCard title="Inventory movements" subtitle={bundle.movements.formula || "Unit waterfall for the selected window."}>
          {bundle.movements.opening_units == null ? (
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
                      <Cell key={step.name} fill={step.kind === "down" ? "var(--color-risk)" : step.kind === "up" ? "var(--color-forecast)" : "var(--color-primary)"} />
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
            <ComposedChart data={bundle.sales}>
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
              data={bundle.categories}
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
                {bundle.categories.map((row) => (
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
        <p className="card-sub">{bundle.abcRule}</p>
        <p className="card-sub">{bundle.xyzRule}</p>
        <div className="abc-grid" role="grid" aria-label="ABC XYZ matrix">
          <span />
          {["X", "Y", "Z"].map((xyz) => (
            <strong key={xyz} className="abc-head">{xyz}</strong>
          ))}
          {["A", "B", "C"].map((abc) => (
            <AbcRow key={abc} abc={abc} cells={bundle.cells} selected={query.cell} onSelect={(cell) => update({ cell: query.cell === cell ? undefined : cell })} />
          ))}
        </div>
        {query.cell ? (
          <div className="chip-row">
            <span className="chip">{query.cell}: {bundle.cells.find((cell) => cell.cell === query.cell)?.interpretation}</span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => update({ cell: undefined })}>Clear cell</button>
          </div>
        ) : null}
        <DataTable
          rows={cellProducts.slice(0, 12)}
          onSelect={(row) => onProductSelect(row.product_id)}
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
        <p className="card-sub">{bundle.slowDefinition}</p>
        {bundle.slow.length ? (
          <DataTable
            rows={bundle.slow}
            onSelect={(row) => onProductSelect(row.product_id)}
            columns={[
              { key: "product", header: "Product", render: (row) => `${row.name} · ${row.sku}` },
              { key: "historical", header: "Historical stock", align: "right", render: (row) => formatNumber(row.historical_stock_units ?? row.stock_units) },
              { key: "current", header: "Current stock", align: "right", render: (row) => formatNumber(row.current_stock_units ?? row.stock_units) },
              { key: "sales", header: "Sold 30 / 90", align: "right", render: (row) => `${formatNumber(row.sold_units_30d)} / ${formatNumber(row.sold_units_90d)}` },
              { key: "cover", header: "Current forecast cover", align: "right", render: (row) => (row.forecast_days_of_supply == null ? "N/A" : `${row.forecast_days_of_supply.toFixed(0)} d`) },
              { key: "action", header: "Suggested action", render: (row) => row.suggested_action },
            ]}
          />
        ) : (
          <EmptyState title="No slow-moving SKUs in this filter" message="The screen found no stock that met the documented rules." />
        )}
      </section>

      <section className="card" style={{ marginBottom: 16 }}>
        <h2 className="card-title">Supplier intelligence</h2>
        <p className="card-sub">{bundle.catalogNote}</p>
        <p className="card-sub">{bundle.supplierNote}</p>
        <div className="supplier-grid">
          {bundle.suppliers.map((supplier) => (
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
  );
}
