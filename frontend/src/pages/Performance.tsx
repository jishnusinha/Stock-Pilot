import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import { ChartCard } from "../components/ChartCard";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { useApi } from "../hooks/useApi";
import { formatDate } from "../utils/dates";
import { formatNumber, formatPaise, NOT_MEASURED } from "../utils/format";

export function Performance() {
  const { data, loading, error, offline, reload } = useApi((s) => api.performance(s), []);

  if (loading && !data) return <p>Loading performance metrics…</p>;
  if (error && !data) return <ErrorState message={error} onRetry={reload} offline={offline} />;

  const kpis = data?.kpis ?? [];
  const top4 = kpis.slice(0, 4);
  while (top4.length < 4) {
    top4.push({
      id: `empty-${top4.length}`,
      label: "Pending evaluation",
      value: NOT_MEASURED,
      measured: false,
    });
  }

  return (
    <>
      <header className="page-header">
        <h1>Model Performance</h1>
        <p className="subtitle">
          Measured holdout metrics · Business outcomes are illustrative simulation
        </p>
      </header>

      <div className="grid-kpi-4">
        {top4.map((k) => (
          <KpiCard
            key={k.id}
            label={k.label}
            value={formatKpiValue(k.value, k.unit)}
            sublabel={k.measured ? k.source ?? "Measured on holdout" : "Run python -m app.cli evaluate"}
          />
        ))}
      </div>

      <div className="grid-2-1">
        <ChartCard title="Backtest: actual vs predicted" subtitle="Chronological holdout demand">
          {(data?.backtest_series?.length ?? 0) === 0 ? (
            <EmptyState
              title="No backtest series"
              message="Run backend evaluation: python -m app.cli evaluate"
            />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={data?.backtest_series}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => formatDate(d).slice(0, 6)} />
                <YAxis width={48} tick={{ fontSize: 10 }} />
                <Tooltip labelFormatter={(l) => formatDate(String(l))} />
                <Legend />
                <Line dataKey="actual" stroke="var(--color-primary)" dot={false} name="Actual" />
                <Line dataKey="predicted" stroke="var(--color-forecast)" strokeDasharray="4 4" dot={false} name="Predicted" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <section className="card">
          <h2 className="card-title">Forecast interval calibration</h2>
          <p style={{ fontSize: 13 }}>
            Nominal band: {data?.coverage?.nominal ?? "p10–p90 (80%)"}
          </p>
          <p style={{ fontSize: 13 }}>
            Empirical coverage:{" "}
            {data?.coverage?.empirical != null
              ? `${(data.coverage.empirical * 100).toFixed(1)}%`
              : "Insufficient holdout samples"}
          </p>
          <p style={{ fontSize: 13 }}>
            Pinball loss:{" "}
            {data?.coverage?.pinball_loss != null
              ? formatNumber(data.coverage.pinball_loss)
              : NOT_MEASURED}
          </p>
        </section>
      </div>

      <section className="card" style={{ marginBottom: 16 }}>
        <h2 className="card-title">Baseline comparison (forecast WAPE)</h2>
        {(data?.baseline_comparison?.length ?? 0) === 0 ? (
          <EmptyState title="No baselines" message="Evaluation exports comparison table." />
        ) : (
          <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--color-border)", textAlign: "left" }}>
                <th style={{ padding: 8 }}>Model</th>
                <th style={{ padding: 8 }}>WAPE</th>
                <th style={{ padding: 8 }}>MAE</th>
              </tr>
            </thead>
            <tbody>
              {data?.baseline_comparison?.map((b) => (
                <tr key={b.name} style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <td style={{ padding: 8 }}>{b.name}</td>
                  <td className="tabular" style={{ padding: 8 }}>
                    {b.wape != null ? `${(b.wape * 100).toFixed(2)}%` : NOT_MEASURED}
                  </td>
                  <td className="tabular" style={{ padding: 8 }}>
                    {b.mae != null ? formatNumber(b.mae) : NOT_MEASURED}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card" style={{ marginBottom: 16 }}>
        <h2 className="card-title">Model versions</h2>
        <DataTable
          rows={data?.model_versions ?? []}
          columns={[
            { key: "name", header: "Agent", render: (r) => r.name },
            { key: "ver", header: "Version", render: (r) => r.version ?? "—" },
            {
              key: "trained",
              header: "Trained",
              render: (r) => (r.trained_at ? formatDate(r.trained_at) : "—"),
            },
            { key: "status", header: "Status", render: (r) => r.status },
            { key: "src", header: "Source", render: (r) => r.source ?? "local" },
          ]}
        />
      </section>

      {data?.business_simulation ? (
        <section className="card">
          <h2 className="card-title">{data.business_simulation.label}</h2>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 12 }}>
            Illustrative simulation savings — not measured operational ROI
          </p>
          <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--color-border)", textAlign: "left" }}>
                <th style={{ padding: 8 }}>Strategy</th>
                <th style={{ padding: 8 }}>Simulated savings</th>
                <th style={{ padding: 8 }}>Note</th>
              </tr>
            </thead>
            <tbody>
              {data.business_simulation.rows.map((row) => (
                <tr key={row.strategy} style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <td style={{ padding: 8 }}>{row.strategy}</td>
                  <td style={{ padding: 8 }}>
                    {row.savings_paise != null ? formatPaise(row.savings_paise) : "N/A"}
                  </td>
                  <td style={{ padding: 8, color: "var(--color-text-muted)" }}>{row.note ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </>
  );
}

function formatKpiValue(value: number | string | null, unit?: string) {
  if (value == null || value === NOT_MEASURED) return NOT_MEASURED;
  if (typeof value === "number") {
    if (unit === "%") return `${(value * 100).toFixed(2)}%`;
    if (unit === "paise") return formatPaise(value);
    return formatNumber(value);
  }
  return value;
}
