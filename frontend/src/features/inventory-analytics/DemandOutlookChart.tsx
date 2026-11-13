import { useMemo } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Area,
} from "recharts";
import { ChartCard } from "../../components/ChartCard";
import { EmptyState } from "../../components/EmptyState";
import type { PredictiveDemand } from "../../types/api";
import { formatNumber } from "../../utils/format";
import type { PredictiveHorizon } from "../../utils/analyticsQuery";
import { SegmentedControl } from "../../components/Controls";

export function DemandOutlookChart({
  data,
  forecastAsOf,
  horizon,
  onHorizonChange,
}: {
  data: PredictiveDemand | null;
  forecastAsOf?: string | null;
  horizon: PredictiveHorizon;
  onHorizonChange: (h: PredictiveHorizon) => void;
}) {
  const series = data?.series ?? [...(data?.history ?? []), ...(data?.forecast ?? [])];
  const splitIndex = useMemo(() => series.findIndex((row) => row.is_forecast), [series]);
  const chartData = useMemo(
    () =>
      series.map((row) => {
        const hasBand = row.is_forecast && row.p10 != null && row.p90 != null;
        return {
          date: row.date,
          actual_units: row.actual_units ?? null,
          p50: row.p50 ?? null,
          p10: row.p10 ?? null,
          p90: row.p90 ?? null,
          is_forecast: Boolean(row.is_forecast),
          bandLo: hasBand ? Number(row.p10) : null,
          bandSpan: hasBand ? Number(row.p90) - Number(row.p10) : null,
        };
      }),
    [series],
  );

  if (!data?.ready) {
    return (
      <ChartCard title="Demand outlook" subtitle={`Forecast as-of ${forecastAsOf ?? "—"}`}>
        <EmptyState title="Demand forecast unavailable" message={data?.note ?? "No persisted forecast for this cohort."} />
      </ChartCard>
    );
  }

  return (
    <ChartCard
      title="Demand outlook"
      subtitle={`Historical fulfilled demand, then forecast from ${forecastAsOf ?? data.forecast_as_of ?? "—"}. Cohort band is a sum-of-SKU heuristic.`}
      actions={
        <SegmentedControl<PredictiveHorizon>
          label="Forecast horizon"
          value={horizon}
          onChange={onHorizonChange}
          options={[
            { id: "7", label: "7d" },
            { id: "14", label: "14d" },
            { id: "28", label: "28d" },
          ]}
        />
      }
      ariaLabel="Demand history and forecast"
    >
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData} margin={{ right: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} minTickGap={24} />
          <YAxis tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={48} />
          {splitIndex > 0 && forecastAsOf ? (
            <ReferenceLine x={series[splitIndex]?.date} stroke="var(--color-forecast)" strokeDasharray="4 4" label={{ value: "Forecast", position: "insideTopRight", fill: "var(--color-text-muted)", fontSize: 10 }} />
          ) : null}
          <Tooltip content={<DemandTip aggregation={data.aggregation} intervalNote={data.interval_note} />} />
          <Area type="monotone" dataKey="bandLo" stackId="band" stroke="none" fill="transparent" connectNulls={false} isAnimationActive={false} />
          <Area type="monotone" dataKey="bandSpan" stackId="band" stroke="none" fill="var(--color-forecast)" fillOpacity={0.12} name="p10–p90 (heuristic)" connectNulls={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="actual_units" name="Actual units" stroke="var(--color-primary)" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="p50" name="Forecast p50" stroke="var(--color-forecast)" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      {data.interval_note ? <p className="note">{data.interval_note}</p> : null}
    </ChartCard>
  );
}

function DemandTip({
  active,
  payload,
  aggregation,
  intervalNote,
}: {
  active?: boolean;
  payload?: Array<{ payload: { date: string; actual_units?: number; p50?: number; p10?: number; p90?: number; is_forecast?: boolean } }>;
  aggregation?: string;
  intervalNote?: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.date}</strong>
      {row.is_forecast ? <div>Forecast slice</div> : <div>Historical actual</div>}
      {row.actual_units != null ? <div>Actual {formatNumber(row.actual_units)}</div> : null}
      {row.p50 != null ? <div>p50 {formatNumber(row.p50)}</div> : null}
      {row.p10 != null && row.p90 != null ? <div>p10–p90 {formatNumber(row.p10)} – {formatNumber(row.p90)}</div> : null}
      {aggregation === "cohort_sum" ? <div className="note">Summed SKU quantiles — heuristic band.</div> : null}
      {intervalNote ? <div className="note">{intervalNote}</div> : null}
    </div>
  );
}
