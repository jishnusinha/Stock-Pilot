import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "../../components/ChartCard";
import { DataTable } from "../../components/DataTable";
import { EmptyState } from "../../components/EmptyState";
import type { PredictiveRisks } from "../../types/api";
import { formatNumber, formatPaise } from "../../utils/format";

const BAND_COLORS: Record<string, string> = {
  high: "var(--color-risk)",
  moderate: "var(--color-warning)",
  low: "var(--color-primary)",
  unavailable: "var(--color-border)",
};

export function StockoutRiskPanel({
  data,
  onSelectProduct,
}: {
  data: PredictiveRisks | null;
  onSelectProduct: (id: number) => void;
}) {
  if (!data?.ready) {
    return (
      <section className="card">
        <h2 className="card-title">Stockout risk</h2>
        <EmptyState title="Risk view unavailable" message={data?.note ?? "Risk cache missing for this cohort."} />
      </section>
    );
  }

  const distribution = data.distribution ?? {};
  const distRows = Object.entries(distribution).map(([band, count]) => ({ band, count }));
  const categories = (data.categories ?? []).slice(0, 8);

  return (
    <section className="card risk-panel">
      <h2 className="card-title">Stockout risk</h2>
      <p className="card-sub">
        {data.aggregation_note ?? data.thresholds?.definition}
        {data.operational_high_risk_level_count != null
          ? ` Cache risk_level=high: ${data.operational_high_risk_level_count} SKUs (includes short days-of-supply). Probability band high: ${data.at_risk_count ?? 0}.`
          : null}
      </p>
      <div className="analytics-split">
        <ChartCard title="Risk distribution" subtitle="Counts by band — probabilities are never summed." ariaLabel="Stockout risk distribution">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={distRows}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="band" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={32} />
              <Tooltip formatter={(v) => formatNumber(typeof v === "number" ? v : 0)} />
              <Bar dataKey="count" name="SKUs" radius={[6, 6, 0, 0]}>
                {distRows.map((row) => (
                  <Cell key={row.band} fill={BAND_COLORS[row.band] ?? "var(--color-primary)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="At-risk by category" subtitle="High-band SKU counts per category.">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={categories} layout="vertical" margin={{ left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} />
              <YAxis type="category" dataKey="category" width={88} tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} />
              <Tooltip />
              <Bar dataKey="at_risk_skus" name="At-risk SKUs" fill="var(--color-risk)" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
      <h3 className="card-sub">High-priority SKUs</h3>
      <DataTable
        rows={data.products ?? []}
        onSelect={(row) => onSelectProduct(row.product_id)}
        columns={[
          { key: "sku", header: "Product", render: (row) => `${row.name} · ${row.sku}` },
          { key: "band", header: "Band", render: (row) => row.risk_band },
          {
            key: "risk",
            header: "Stockout risk",
            align: "right",
            render: (row) => (row.stockout_risk == null ? "N/A" : `${(row.stockout_risk * 100).toFixed(0)}%`),
          },
          { key: "dos", header: "Days of supply", align: "right", render: (row) => (row.days_of_supply == null ? "N/A" : row.days_of_supply.toFixed(0)) },
          { key: "qty", header: "Suggested qty", align: "right", render: (row) => (row.suggested_qty == null ? "—" : formatNumber(row.suggested_qty)) },
          { key: "cost", header: "Est. cost", align: "right", render: (row) => (row.estimated_cost_paise == null ? "—" : formatPaise(row.estimated_cost_paise)) },
        ]}
      />
    </section>
  );
}
