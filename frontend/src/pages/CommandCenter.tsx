import { useNavigate } from "react-router-dom";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
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
import { RiskBadge } from "../components/Badge";
import { SkeletonCard } from "../components/Skeleton";
import { useApi } from "../hooks/useApi";
import type { RiskSkuRow } from "../types/api";
import { DEMO_SNAPSHOT_LABEL, formatDate } from "../utils/dates";
import { formatNumber, formatPaise, formatPercent } from "../utils/format";

export function CommandCenter() {
  const navigate = useNavigate();
  const { data, loading, error, offline, reload } = useApi(
    (s) => api.dashboard(s),
    [],
  );

  async function createReorder() {
    const rec = data?.recommendation;
    if (!rec?.id) {
      navigate(`/simulator?product=${rec?.product_id ?? ""}`);
      return;
    }
    try {
      await api.proposeRecommendation(rec.id);
      navigate("/reorders");
    } catch {
      navigate(`/inventory?product=${rec.product_id}`);
    }
  }

  if (loading && !data) {
    return (
      <>
        <PageHeader />
        <div className="grid-kpi-4">
          {[1, 2, 3, 4].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </>
    );
  }

  if (error && !data) {
    return (
      <>
        <PageHeader />
        <ErrorState message={error} onRetry={reload} offline={offline} />
      </>
    );
  }

  const kpis = data?.kpis;
  const series = data?.forecast_series ?? [];

  return (
    <>
      <PageHeader asOf={data?.as_of} />
      <div className="grid-kpi-4">
        <KpiCard
          label="Projected revenue"
          value={formatPaise(kpis?.projected_revenue_paise)}
          sublabel="Next 30 days (forecast)"
          trend={
            kpis?.projected_revenue_trend_pct != null
              ? formatPercent(kpis.projected_revenue_trend_pct)
              : null
          }
        />
        <KpiCard
          label="At-risk products"
          value={formatNumber(kpis?.at_risk_products)}
          sublabel="May stock out ≤ 14 days"
          trend={
            kpis?.at_risk_delta != null ? `+${kpis.at_risk_delta}` : undefined
          }
          trendVariant="risk"
        />
        <KpiCard
          label="Suggested reorders"
          value={formatNumber(kpis?.suggested_reorders)}
          sublabel="From optimizer"
          trend={
            kpis?.reorders_trend_pct != null
              ? formatPercent(kpis.reorders_trend_pct)
              : null
          }
        />
        <KpiCard
          label="Est. savings"
          value={
            kpis?.estimated_savings_paise != null
              ? formatPaise(kpis.estimated_savings_paise)
              : kpis?.savings_label ?? "Simulation estimate"
          }
          sublabel={kpis?.savings_label ?? "Illustrative simulation"}
          trend={
            kpis?.savings_trend_pct != null
              ? formatPercent(kpis.savings_trend_pct)
              : null
          }
        />
      </div>

      <div className="grid-2-1">
        <ChartCard
          title="Demand forecast"
          subtitle="Actual history + 28-day ML forecast · p10–p90 nominal 80% band"
          ariaLabel="Demand forecast chart with uncertainty band"
        >
          {series.length === 0 ? (
            <EmptyState title="No forecast data" message="Run backend bootstrap to populate forecasts." />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => formatDate(d).slice(0, 6)} />
                <YAxis tick={{ fontSize: 11 }} width={48} />
                <Tooltip labelFormatter={(l) => formatDate(String(l))} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="p90"
                  stackId="band"
                  stroke="none"
                  fill="rgba(37, 99, 235, 0.08)"
                  name="p90"
                />
                <Area
                  type="monotone"
                  dataKey="p10"
                  stackId="band2"
                  stroke="none"
                  fill="var(--color-bg)"
                  name="p10"
                />
                <Line
                  type="monotone"
                  dataKey="actual"
                  stroke="var(--color-primary)"
                  dot={false}
                  name="Actual"
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="p50"
                  stroke="var(--color-forecast)"
                  strokeDasharray="5 5"
                  dot={false}
                  name="Forecast p50"
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <StackAside>
          <AlertsCard alerts={data?.alerts ?? []} navigate={navigate} />
          <RecommendationCard
            rec={data?.recommendation}
            onCreate={createReorder}
            onDetails={() =>
              data?.recommendation?.product_id &&
              navigate(`/inventory?product=${data.recommendation.product_id}`)
            }
          />
        </StackAside>
      </div>

      <section className="card">
        <h2 className="card-title">Top products at risk</h2>
        {(data?.top_risk?.length ?? 0) === 0 ? (
          <EmptyState title="No at-risk SKUs" message="Risk scores update from latest forecasts." />
        ) : (
          <DataTable<RiskSkuRow>
            rows={data?.top_risk ?? []}
            columns={[
              {
                key: "name",
                header: "Product",
                render: (r) => (
                  <div>
                    <strong>{r.name}</strong>
                    <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{r.sku}</div>
                  </div>
                ),
              },
              {
                key: "stock",
                header: "Stock",
                align: "right",
                render: (r) => formatNumber(r.current_stock),
              },
              {
                key: "dos",
                header: "Days supply",
                align: "right",
                render: (r) =>
                  r.days_of_supply != null ? formatNumber(r.days_of_supply) : "N/A",
              },
              {
                key: "fc",
                header: "Forecast (4 wk)",
                align: "right",
                render: (r) =>
                  r.forecast_4wk_units != null ? formatNumber(r.forecast_4wk_units) : "N/A",
              },
              {
                key: "risk",
                header: "Risk",
                render: (r) => <RiskBadge level={r.risk_level} />,
              },
            ]}
            onSelect={(r) => navigate(`/inventory?product=${r.product_id}`)}
          />
        )}
      </section>
    </>
  );
}

function PageHeader({ asOf }: { asOf?: string }) {
  return (
    <header className="page-header">
      <h1>Command Center</h1>
      <p className="subtitle">
        ML-driven inventory overview · {asOf ? formatDate(asOf) : DEMO_SNAPSHOT_LABEL}
      </p>
    </header>
  );
}

function AlertsCard({
  alerts,
  navigate,
}: {
  alerts: { id: string; severity: string; title: string; message: string; product_id?: number | null }[];
  navigate: (p: string) => void;
}) {
  return (
    <SideCard title="Critical alerts">
      {alerts.length === 0 ? (
        <p style={{ color: "var(--color-text-muted)", fontSize: 13 }}>No critical alerts.</p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {alerts.map((a) => (
            <li key={a.id} style={{ marginBottom: 12, fontSize: 13 }}>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ width: "100%", textAlign: "left", justifyContent: "flex-start" }}
                onClick={() =>
                  a.product_id
                    ? navigate(`/inventory?product=${a.product_id}`)
                    : undefined
                }
              >
                <strong>{a.title}</strong>
                <div style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>{a.message}</div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </SideCard>
  );
}

function RecommendationCard({
  rec,
  onCreate,
  onDetails,
}: {
  rec?: { title: string; message: string; suggested_qty?: number | null; impact_label?: string } | null;
  onCreate: () => void;
  onDetails: () => void;
}) {
  if (!rec) {
    return (
      <SideCard title="StockPilot recommendation">
        <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>No active recommendation.</p>
      </SideCard>
    );
  }
  return (
    <SideCard title="StockPilot recommendation">
      {rec.impact_label ? (
        <span style={{ fontSize: 11, color: "var(--color-primary)", fontWeight: 600 }}>{rec.impact_label}</span>
      ) : null}
      <p style={{ fontWeight: 600, margin: "8px 0" }}>{rec.title}</p>
      <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>{rec.message}</p>
      {rec.suggested_qty != null ? (
        <p className="tabular" style={{ fontSize: 13 }}>
          Suggested qty: {formatNumber(rec.suggested_qty)} units
        </p>
      ) : null}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
        <button type="button" className="btn btn-primary" onClick={onCreate}>
          Create draft reorder
        </button>
        <button type="button" className="btn btn-secondary" onClick={onDetails}>
          View details
        </button>
      </div>
    </SideCard>
  );
}

function StackAside({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>{children}</div>;
}

function SideCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h2 className="card-title">{title}</h2>
      {children}
    </div>
  );
}
