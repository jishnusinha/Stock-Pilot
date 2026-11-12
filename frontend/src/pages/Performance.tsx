import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
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
import { PageHeader, ProgressBar } from "../components/Controls";
import { SkeletonCard } from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import { formatDate } from "../utils/dates";
import { formatLatencyMs, formatNumber, formatPaise, NOT_MEASURED } from "../utils/format";

export function Performance() {
  const { data, loading, error, offline, reload } = useApi((s) => api.performance(s), []);
  const [family, setFamily] = useState("all");

  const versions = useMemo(() => {
    const rows = data?.model_versions ?? [];
    if (family === "all") return rows;
    return rows.filter((row) => row.name.toLowerCase().includes(family));
  }, [data?.model_versions, family]);

  if (loading && !data) {
    return (
      <>
        <PageHeader title="Model Performance" subtitle="Loading evaluation…" />
        <div className="grid-kpi-4">
          {[1, 2, 3, 4].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </>
    );
  }
  if (error && !data) return <ErrorState message={error} onRetry={reload} offline={offline} />;

  const kpis = data?.kpis ?? [];
  const coverage = data?.coverage;
  const empiricalPct = coverage?.empirical != null ? coverage.empirical * 100 : null;

  return (
    <>
      <PageHeader
        title="Model Performance"
        subtitle={`Measured evaluation on synthetic data${data?.evaluation_mode ? ` · ${data.evaluation_mode}` : ""}. Category and SKU accuracy are not stored separately, so WAPE is pooled. Business rows are a simulated policy replay${data?.business_simulation?.sample_skus != null ? ` on ${data.business_simulation.sample_skus} SKUs` : ""} and do not prove multi-agent superiority.`}
        actions={
          <select className="select" style={{ width: "auto" }} aria-label="Model filter" value={family} onChange={(e) => setFamily(e.target.value)}>
            <option value="all">All agents</option>
            <option value="demand">Demand</option>
            <option value="risk">Risk</option>
            <option value="price">Price</option>
            <option value="supplier">Supplier</option>
          </select>
        }
      />

      <div className="grid-kpi-4">
        {kpis.slice(0, 4).map((k) => (
          <KpiCard
            key={k.id}
            label={k.label}
            value={formatKpiValue(k.value, k.unit)}
            sublabel={k.measured ? k.tooltip ?? k.source ?? "Measured" : "Not measured"}
          />
        ))}
      </div>

      <div className="perf-grid">
        <ChartCard title="Baseline comparison" subtitle="Forecast error on the same holdout. Lower WAPE is better. No winner is claimed beyond these numbers.">
          {(data?.baseline_comparison?.length ?? 0) === 0 ? (
            <EmptyState title="No baselines" message="Run python -m app.cli evaluate to write the comparison." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={data?.baseline_comparison} layout="vertical" margin={{ left: 16, right: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis type="number" tickFormatter={(v) => `${(Number(v) * 100).toFixed(0)}%`} />
                <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => (typeof v === "number" ? `${(v * 100).toFixed(2)}%` : String(v))} />
                <Bar dataKey="wape" fill="#0b6b3a" name="WAPE" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard
          title="Backtest: actual vs predicted"
          subtitle="Rolling one-step holdout points. This is not a multi-horizon forecast chart."
        >
          {(data?.backtest_series?.length ?? 0) === 0 ? (
            <EmptyState title="No backtest series" message="Evaluation has not written a series yet." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={data?.backtest_series}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => formatDate(String(d)).slice(0, 6)} minTickGap={20} />
                <YAxis width={40} tick={{ fontSize: 10 }} />
                <Tooltip labelFormatter={(l) => formatDate(String(l))} />
                <Legend />
                <Line dataKey="actual" stroke="var(--color-primary)" dot={false} name="Actual" strokeWidth={2} />
                <Line dataKey="predicted" stroke="var(--color-forecast)" strokeDasharray="4 3" dot={false} name="Predicted" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <section className="card">
          <h2 className="card-title">Forecast uncertainty</h2>
          <p className="card-sub">Nominal interval versus what the holdout actually covered.</p>
          <div style={{ marginTop: 14, display: "grid", gap: 12 }}>
            <div>
              <div className="note" style={{ marginTop: 0 }}>Nominal: {coverage?.nominal ?? "p10–p90 (80%)"}</div>
              <ProgressBar value={80} label="Nominal 80 percent coverage" />
            </div>
            <div>
              <div className="note">
                Empirical: {empiricalPct != null ? `${empiricalPct.toFixed(1)}%` : "Not measured"}
              </div>
              <ProgressBar value={empiricalPct ?? 0} tone="info" label="Empirical coverage" />
            </div>
            <div className="stat-tile">
              <div className="lbl">Quantile / pinball loss</div>
              <div className="val">{coverage?.pinball_loss != null ? formatNumber(coverage.pinball_loss) : NOT_MEASURED}</div>
            </div>
          </div>
        </section>
      </div>

      <section className="card" style={{ padding: 0, marginBottom: 16 }}>
        <div className="card-head" style={{ padding: "16px 16px 0" }}>
          <div>
            <h2 className="card-title">Model registry</h2>
            <p className="card-sub">{versions.length} shown · training source is local synthetic data</p>
          </div>
        </div>
        <DataTable
          rows={versions}
          columns={[
            { key: "name", header: "Agent", render: (r) => r.name.replaceAll("_", " ") },
            { key: "ver", header: "Version", render: (r) => r.version ?? "—" },
            { key: "trained", header: "Trained", render: (r) => (r.trained_at ? formatDate(r.trained_at) : "—") },
            { key: "status", header: "Status", render: (r) => r.status },
            { key: "src", header: "Source", render: (r) => r.source ?? "local" },
          ]}
        />
      </section>

      {data?.business_simulation ? (
        <section className="card">
          <div className="card-head">
            <div>
              <h2 className="card-title">Policy replay</h2>
              <p className="card-sub">
                {data.business_simulation.label}. Mean defined cost is holding plus shortage on simulated paths. It is not purchasing spend and it is not realized savings.
                {data.business_simulation.note ? ` ${data.business_simulation.note}` : ""}
              </p>
            </div>
          </div>
          {(data.business_simulation.rows?.length ?? 0) === 0 ? (
            <EmptyState title="No policy replay" message="Evaluate to compare fixed, demand-only, and multi-agent policies." />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={data.business_simulation.rows}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="strategy" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} width={48} />
                  <Tooltip formatter={(v) => (typeof v === "number" ? formatPaise(v) : String(v ?? ""))} />
                  <Bar dataKey="cost_paise" name="Mean defined cost" fill="#0b6b3a" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Strategy</th>
                      <th>Mean defined cost</th>
                      <th>Mean stockout days</th>
                      <th>Mean unmet units</th>
                      <th>Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.business_simulation.rows.map((row) => (
                      <tr key={row.strategy}>
                        <td>{row.strategy}</td>
                        <td className="tabular">{row.cost_paise != null ? formatPaise(row.cost_paise) : "N/A"}</td>
                        <td className="tabular">{row.mean_stockout_days != null ? formatNumber(row.mean_stockout_days) : "—"}</td>
                        <td className="tabular">{row.mean_unmet_demand_units != null ? formatNumber(row.mean_unmet_demand_units) : "—"}</td>
                        <td>{row.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      ) : null}

      <section className="card">
        <h2 className="card-title">Measured agent step time</h2>
        <p className="card-sub">Durations stored on agent runs. API latency above is a separate local measurement and stays “Not measured” until a benchmark file exists.</p>
        {data?.api_benchmark?.method ? (
          <p className="note">
            {data.api_benchmark.method}
            {data.api_benchmark.measured_at ? ` Measured ${data.api_benchmark.measured_at}.` : ""}
          </p>
        ) : null}
        {(data?.agent_latency?.length ?? 0) === 0 ? (
          <p className="note">No timed agent runs are stored yet.</p>
        ) : (
          <DataTable
            rows={data?.agent_latency ?? []}
            columns={[
              { key: "agent", header: "Agent", render: (row) => row.agent_name.replaceAll("_", " ") },
              { key: "runs", header: "Runs", align: "right", render: (row) => formatNumber(row.runs) },
              { key: "mean", header: "Mean", align: "right", render: (row) => formatLatencyMs(row.mean_duration_ms) },
              { key: "max", header: "Max", align: "right", render: (row) => formatLatencyMs(row.max_duration_ms) },
            ]}
          />
        )}
      </section>

      {data?.expanded_policy_replay?.rows?.length ? (
        <section className="card" style={{ marginTop: 16 }}>
          <h2 className="card-title">Expanded simulated policy replay</h2>
          <p className="card-sub">
            {data.expanded_policy_replay.limitation} Sample {formatNumber(data.expanded_policy_replay.sample_skus)} SKUs
            {data.expanded_policy_replay.runtime_seconds != null ? `, runtime ${data.expanded_policy_replay.runtime_seconds}s` : ""}.
            Purchasing cash is not included in defined cost.
          </p>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Mean defined cost</th>
                  <th>Mean stockout days</th>
                  <th>Mean unmet units</th>
                  <th>Mean purchasing cash</th>
                </tr>
              </thead>
              <tbody>
                {data.expanded_policy_replay.rows.map((row) => (
                  <tr key={row.strategy}>
                    <td>{row.strategy}</td>
                    <td className="tabular">{row.cost_paise != null ? formatPaise(row.cost_paise) : "N/A"}</td>
                    <td className="tabular">{row.mean_stockout_days != null ? formatNumber(row.mean_stockout_days) : "—"}</td>
                    <td className="tabular">{row.mean_unmet_demand_units != null ? formatNumber(row.mean_unmet_demand_units) : "—"}</td>
                    <td className="tabular">{row.mean_purchasing_cash_paise != null ? formatPaise(row.mean_purchasing_cash_paise) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {data?.mlops?.limitations?.length ? (
        <section className="card" style={{ marginTop: 16 }}>
          <h2 className="card-title">What this screen does not claim</h2>
          <ul className="insight-list">
            {data.mlops.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

function formatKpiValue(value: number | string | null, unit?: string) {
  if (value == null || value === NOT_MEASURED || value === "N/A" || value === "Not measured") return NOT_MEASURED;
  if (typeof value === "number") {
    if (unit === "%") return `${(value * 100).toFixed(2)}%`;
    if (unit === "ratio") return `${(value * 100).toFixed(1)}%`;
    if (unit === "paise") return formatPaise(value);
    if (unit === "ms") return formatLatencyMs(value);
    return formatNumber(value);
  }
  return value;
}
