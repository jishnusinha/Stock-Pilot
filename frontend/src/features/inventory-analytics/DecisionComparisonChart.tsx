import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "../../components/ChartCard";
import { EmptyState } from "../../components/EmptyState";
import type { PredictiveExplain } from "../../types/api";
import { formatPaise, formatNumber } from "../../utils/format";
import { compactPaise } from "./utils";

export function DecisionComparisonChart({ explain, loading }: { explain: PredictiveExplain | null; loading?: boolean }) {
  if (loading) {
    return (
      <ChartCard title="Decision comparison" subtitle="Loading projection comparison…">
        <p className="note">Fetching explain endpoint…</p>
      </ChartCard>
    );
  }

  if (!explain?.ready) {
    return (
      <ChartCard title="Decision comparison" subtitle="Select a product with open recommendations.">
        <EmptyState title="No comparison yet" message="Open Explain on a recommendation row or filter to a single product." />
      </ChartCard>
    );
  }

  const base = explain.comparison?.no_reorder?.series ?? [];
  const rec = explain.comparison?.recommended?.series ?? [];
  const byDate = new Map<string, { date: string; no_reorder?: number; recommended?: number }>();
  base.forEach((row) => {
    byDate.set(row.date, { date: row.date, no_reorder: row.projected_inventory_value_paise });
  });
  rec.forEach((row) => {
    const existing = byDate.get(row.date) ?? { date: row.date };
    existing.recommended = row.projected_inventory_value_paise;
    byDate.set(row.date, existing);
  });
  const chartData = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));

  return (
    <ChartCard
      title={`Decision comparison · ${explain.product.sku}`}
      subtitle={explain.comparison?.label ?? "Simulated inventory trajectories — not realized outcomes."}
    >
      <p className="note">
        Ending value — no reorder {formatPaise(explain.comparison?.no_reorder?.ending_inventory_value_paise)} vs recommended{" "}
        {formatPaise(explain.comparison?.recommended?.ending_inventory_value_paise)}. Unmet demand{" "}
        {formatNumber(explain.comparison?.no_reorder?.total_unmet_demand_units ?? 0)} →{" "}
        {formatNumber(explain.comparison?.recommended?.total_unmet_demand_units ?? 0)} units.
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} />
          <YAxis tickFormatter={(v) => compactPaise(Number(v))} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={56} />
          <Tooltip formatter={(v) => formatPaise(typeof v === "number" ? v : null)} />
          <Legend />
          <Line type="monotone" dataKey="no_reorder" name="No reorder" stroke="var(--color-primary)" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="recommended" name="Recommended" stroke="var(--color-forecast)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
      {explain.recommendation?.explanation ? <p className="note">{explain.recommendation.explanation}</p> : null}
    </ChartCard>
  );
}
