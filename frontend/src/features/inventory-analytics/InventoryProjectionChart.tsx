import { useMemo } from "react";
import { Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard } from "../../components/ChartCard";
import { EmptyState } from "../../components/EmptyState";
import { SegmentedControl } from "../../components/Controls";
import type { PredictiveProjection } from "../../types/api";
import type { PredictiveHorizon, ProjectionMode } from "../../utils/analyticsQuery";
import { formatNumber, formatPaise } from "../../utils/format";
import { compactPaise } from "./utils";

export function InventoryProjectionChart({
  data,
  forecastAsOf,
  horizon,
  mode,
  onHorizonChange,
  onModeChange,
}: {
  data: PredictiveProjection | null;
  forecastAsOf?: string | null;
  horizon: PredictiveHorizon;
  mode: ProjectionMode;
  onHorizonChange: (h: PredictiveHorizon) => void;
  onModeChange: (m: ProjectionMode) => void;
}) {
  const chartData = useMemo(() => {
    const hist = (data?.history ?? []).map((row) => ({
      date: row.date,
      inventory_value_paise: row.projected_inventory_value_paise ?? row.inventory_value_paise ?? 0,
      projected_inventory_units: row.projected_inventory_units ?? null,
      predicted_demand: null as number | null,
      is_forecast: false,
    }));
    const proj = (data?.series ?? []).map((row) => ({
      date: row.date,
      inventory_value_paise: row.projected_inventory_value_paise ?? 0,
      projected_inventory_units: row.projected_inventory_units ?? null,
      predicted_demand: row.predicted_demand ?? null,
      is_forecast: true,
    }));
    return [...hist, ...proj];
  }, [data]);

  const splitDate = data?.series?.[0]?.date;

  if (!data?.ready) {
    return (
      <ChartCard title="Inventory projection" subtitle={data?.projection_note}>
        <EmptyState title="Projection unavailable" message={data?.note ?? "Forecasts missing for this horizon."} />
      </ChartCard>
    );
  }

  return (
    <ChartCard
      title="Inventory projection"
      subtitle={`Simulated path from ${forecastAsOf ?? data.forecast_as_of ?? "—"} · mode ${mode.replace("_", " ")}`}
      actions={
        <>
          <SegmentedControl<PredictiveHorizon>
            label="Projection horizon"
            value={horizon}
            onChange={onHorizonChange}
            options={[
              { id: "7", label: "7d" },
              { id: "14", label: "14d" },
              { id: "28", label: "28d" },
            ]}
          />
          <SegmentedControl<ProjectionMode>
            label="Projection mode"
            value={mode}
            onChange={onModeChange}
            options={[
              { id: "no_reorder", label: "No reorder" },
              { id: "recommended", label: "Recommended" },
            ]}
          />
        </>
      }
    >
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--color-text-muted)" }} minTickGap={20} />
          <YAxis yAxisId="value" tickFormatter={(v) => compactPaise(Number(v))} tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={56} />
          <YAxis yAxisId="units" orientation="right" tick={{ fontSize: 11, fill: "var(--color-text-muted)" }} width={40} />
          {splitDate ? (
            <ReferenceLine x={splitDate} stroke="var(--color-forecast)" strokeDasharray="4 4" />
          ) : null}
          <Tooltip content={<ProjectionTip />} />
          <Bar yAxisId="value" dataKey="inventory_value_paise" name="Inventory value" radius={[4, 4, 0, 0]}>
            {chartData.map((row) => (
              <Cell key={row.date} fill={row.is_forecast ? "var(--color-forecast)" : "var(--color-primary)"} />
            ))}
          </Bar>
          <Line yAxisId="units" type="monotone" dataKey="projected_inventory_units" name="Projected units" stroke="var(--color-warning)" strokeWidth={2} dot={false} connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
      {data.projection_note ? <p className="note">{data.projection_note}</p> : null}
      {(data.notes ?? []).slice(0, 5).map((note) => (
        <p key={note} className="note">{note}</p>
      ))}
      {(data.notes?.length ?? 0) > 5 ? (
        <p className="note">{data.notes!.length - 5} additional projection notes omitted.</p>
      ) : null}
    </ChartCard>
  );
}

function ProjectionTip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{
    payload: {
      date: string;
      inventory_value_paise?: number;
      projected_inventory_units?: number;
      predicted_demand?: number;
      is_forecast?: boolean;
    };
  }>;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{row.date}</strong>
      <div>{row.is_forecast ? "Projected" : "Historical snapshot"}</div>
      {row.inventory_value_paise != null ? <div>Value {formatPaise(row.inventory_value_paise)}</div> : null}
      {row.projected_inventory_units != null ? <div>Units {formatNumber(row.projected_inventory_units)}</div> : null}
      {row.predicted_demand != null ? <div>Predicted demand {formatNumber(row.predicted_demand)}</div> : null}
    </div>
  );
}
