import { useMemo, useState } from "react";
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
import { AlertTriangle, Bell, IndianRupee, ShoppingCart, Sparkles, TrendingUp } from "lucide-react";
import { api } from "../api/client";
import { ChartCard } from "../components/ChartCard";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { PageHeader, ProgressBar, SegmentedControl } from "../components/Controls";
import { ProvenancePill } from "../components/ProvenancePill";
import { RiskBadge } from "../components/Badge";
import { SkeletonCard } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { useApi } from "../hooks/useApi";
import type { DashboardAlert, DashboardRecommendation, ForecastPoint, RiskSkuRow } from "../types/api";
import { DEMO_SNAPSHOT_LABEL, formatDate } from "../utils/dates";
import { withUncertaintyBand, windowHistory } from "../utils/forecastBand";
import { formatNumber, formatPaise } from "../utils/format";

type WindowId = "30" | "55";

export function CommandCenter() {
  const navigate = useNavigate();
  const toast = useToast();
  const { data, loading, error, offline, reload } = useApi((s) => api.dashboard(s), []);
  const [windowDays, setWindowDays] = useState<WindowId>("55");
  const [creating, setCreating] = useState(false);

  const series = useMemo(() => {
    const raw = data?.forecast_series ?? [];
    return withUncertaintyBand(windowHistory(raw, Number(windowDays)));
  }, [data?.forecast_series, windowDays]);

  async function createReorder() {
    const rec = data?.recommendation;
    if (!rec) return;
    setCreating(true);
    try {
      if (rec.id) {
        await api.proposeRecommendation(rec.id);
        toast.success("Draft reorder created. Stock is unchanged until the order is received.");
        navigate("/reorders");
        return;
      }
      navigate(`/simulator?product=${rec.product_id}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not create a draft reorder");
      navigate(`/inventory?product=${rec.product_id}`);
    } finally {
      setCreating(false);
    }
  }

  if (loading && !data) {
    return (
      <>
        <PageHeader title="Command Center" subtitle="Loading inventory intelligence…" />
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
        <PageHeader title="Command Center" />
        <ErrorState message={error} onRetry={reload} offline={offline} />
      </>
    );
  }

  const kpis = data?.kpis;

  return (
    <>
      <PageHeader
        title="Command Center"
        subtitle="Forecast demand, surface stockout risk, and turn optimizer output into a draft reorder."
        actions={
          <>
            <ProvenancePill />
            <span className="badge badge-muted">{data?.as_of ? `Snapshot ${formatDate(data.as_of)}` : DEMO_SNAPSHOT_LABEL}</span>
          </>
        }
      />

      <div className="grid-kpi-4">
        <KpiCard
          label="Projected revenue"
          icon={<IndianRupee size={16} />}
          value={formatPaise(kpis?.projected_revenue_paise)}
          sublabel="Next 28 days · forecast × price"
          trend={kpis?.projected_revenue_trend_pct != null ? `${kpis.projected_revenue_trend_pct}%` : null}
        />
        <KpiCard
          label="At-risk products"
          icon={<AlertTriangle size={16} />}
          tone="risk"
          value={formatNumber(kpis?.at_risk_products)}
          sublabel="High stockout risk"
          trend={kpis?.at_risk_delta != null ? `${kpis.at_risk_delta > 0 ? "+" : ""}${kpis.at_risk_delta}` : null}
          trendVariant="risk"
        />
        <KpiCard
          label="Suggested reorders"
          icon={<ShoppingCart size={16} />}
          tone="info"
          value={formatNumber(kpis?.suggested_reorders)}
          sublabel="Open optimizer recommendations"
          trend={kpis?.reorders_trend_pct != null ? `${kpis.reorders_trend_pct}%` : null}
        />
        <KpiCard
          label="Simulated impact"
          icon={<Sparkles size={16} />}
          tone="warn"
          value={kpis?.estimated_savings_paise != null ? formatPaise(kpis.estimated_savings_paise) : "N/A"}
          sublabel={kpis?.savings_label ?? "Simulation estimate"}
        />
      </div>

      <div className="grid-2-1">
        <ChartCard
          title="Demand forecast"
          subtitle="Storewide units · history is actual sales · forecast is p50 with a p10–p90 band (nominal 80%)"
          ariaLabel="Demand forecast chart with uncertainty band"
          actions={
            <SegmentedControl<WindowId>
              label="History window"
              value={windowDays}
              onChange={setWindowDays}
              options={[
                { id: "30", label: "30 days" },
                { id: "55", label: "Full history" },
              ]}
            />
          }
        >
          {series.length === 0 ? (
            <EmptyState title="No forecast data" message="Run backend bootstrap to populate forecasts." />
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(d) => formatDate(String(d)).replace(/,?\s*\d{4}/, "")} minTickGap={24} />
                <YAxis tick={{ fontSize: 11 }} width={48} />
                <Tooltip content={<ForecastTooltip />} />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="bandBase"
                  stackId="band"
                  stroke="none"
                  fill="transparent"
                  legendType="none"
                  name="band base"
                  activeDot={false}
                />
                <Area
                  type="monotone"
                  dataKey="bandSpan"
                  stackId="band"
                  stroke="none"
                  fill="rgba(37, 99, 235, 0.18)"
                  name="p10–p90 band"
                  activeDot={false}
                />
                <Line type="monotone" dataKey="actual" stroke="var(--color-primary)" strokeWidth={2.2} dot={false} name="Actual" connectNulls={false} />
                <Line
                  type="monotone"
                  dataKey="p50"
                  stroke="var(--color-forecast)"
                  strokeWidth={2.2}
                  strokeDasharray="5 4"
                  dot={false}
                  name="Forecast p50"
                  connectNulls={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <div className="stack">
          <AlertsCard alerts={data?.alerts ?? []} onOpen={(id) => navigate(`/inventory?product=${id}`)} />
          <RecommendationCard
            rec={data?.recommendation}
            busy={creating}
            onCreate={() => void createReorder()}
            onDetails={() =>
              data?.recommendation && navigate(`/inventory?product=${data.recommendation.product_id}`)
            }
          />
        </div>
      </div>

      <section className="card" style={{ padding: 0 }}>
        <div className="card-head" style={{ padding: "16px 16px 0" }}>
          <div>
            <h2 className="card-title">Top products at risk</h2>
            <p className="card-sub">High and medium risk, shortest cover first</p>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate("/inventory?risk=high")}>
            View inventory
          </button>
        </div>
        {(data?.top_risk?.length ?? 0) === 0 ? (
          <EmptyState title="No at-risk SKUs" message="Risk scores update from the latest forecasts." />
        ) : (
          <DataTable<RiskSkuRow>
            rows={data?.top_risk ?? []}
            onSelect={(r) => navigate(`/inventory?product=${r.product_id}`)}
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
              { key: "category", header: "Category", render: (r) => r.category ?? "—" },
              {
                key: "stock",
                header: "Stock",
                align: "right",
                render: (r) => formatNumber(r.current_stock),
              },
              {
                key: "dos",
                header: "Days of supply",
                render: (r) => <SupplyMeter days={r.days_of_supply} />,
              },
              {
                key: "fc",
                header: "Forecast (4 wk)",
                align: "right",
                render: (r) => (r.forecast_4wk_units != null ? formatNumber(Math.round(r.forecast_4wk_units)) : "N/A"),
              },
              { key: "risk", header: "Risk", render: (r) => <RiskBadge level={r.risk_level} /> },
            ]}
          />
        )}
      </section>
    </>
  );
}

function SupplyMeter({ days }: { days?: number | null }) {
  if (days == null) return <span>N/A</span>;
  const tone = days <= 7 ? "risk" : days <= 14 ? "warn" : "ok";
  return (
    <div style={{ display: "grid", gap: 4, minWidth: 110 }}>
      <span className="tabular">{formatNumber(Math.round(days))} days</span>
      <ProgressBar value={Math.min(100, (days / 30) * 100)} tone={tone} label={`${Math.round(days)} days of supply`} />
    </div>
  );
}

function ForecastTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { payload?: ForecastPoint }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="chart-tip">
      <strong>{formatDate(String(label ?? row.date))}</strong>
      <div>{row.is_forecast ? "Forecast date" : "Historical date"}</div>
      {row.actual != null ? <div className="tabular">Actual: {formatNumber(Math.round(row.actual))}</div> : null}
      {row.p50 != null ? <div className="tabular">p50: {formatNumber(Math.round(row.p50))}</div> : null}
      {row.p10 != null ? <div className="tabular">p10: {formatNumber(Math.round(row.p10))}</div> : null}
      {row.p90 != null ? <div className="tabular">p90: {formatNumber(Math.round(row.p90))}</div> : null}
    </div>
  );
}

function AlertsCard({
  alerts,
  onOpen,
}: {
  alerts: DashboardAlert[];
  onOpen: (productId: number) => void;
}) {
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2 className="card-title">
            <Bell size={16} style={{ verticalAlign: "text-bottom" }} /> Inventory alerts
          </h2>
          <p className="card-sub">{alerts.length ? `${alerts.length} from the risk list` : "None right now"}</p>
        </div>
      </div>
      {alerts.length === 0 ? (
        <p className="note">No critical or warning alerts in the latest dashboard payload.</p>
      ) : (
        alerts.map((alert) => (
          <button
            key={alert.id}
            type="button"
            className={`alert-row ${alert.severity}`}
            onClick={() => alert.product_id && onOpen(alert.product_id)}
          >
            <AlertTriangle size={16} />
            <span>
              <strong>
                {alert.title}: {alert.message}
              </strong>
              <div className="note" style={{ margin: 0 }}>
                Open the product
              </div>
            </span>
          </button>
        ))
      )}
    </section>
  );
}

function RecommendationCard({
  rec,
  busy,
  onCreate,
  onDetails,
}: {
  rec?: DashboardRecommendation | null;
  busy: boolean;
  onCreate: () => void;
  onDetails: () => void;
}) {
  return (
    <section className="card rec-panel">
      <div className="card-head">
        <div>
          <h2 className="card-title">
            <TrendingUp size={16} style={{ verticalAlign: "text-bottom" }} /> Recommendation
          </h2>
          <p className="card-sub">Template text from the optimizer · not a language model</p>
        </div>
        {rec?.impact_label ? <span className="badge badge-mint">{rec.impact_label}</span> : null}
      </div>
      {!rec ? (
        <p className="note">No open recommendation.</p>
      ) : (
        <>
          <p style={{ fontWeight: 650, marginBottom: 6 }}>{rec.title}</p>
          <p className="note" style={{ marginTop: 0 }}>
            {rec.message}
          </p>
          {rec.suggested_qty != null ? (
            <p className="tabular" style={{ fontWeight: 650 }}>
              Suggested quantity: {formatNumber(rec.suggested_qty)} units
            </p>
          ) : null}
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
            <button type="button" className="btn btn-primary" onClick={onCreate} disabled={busy}>
              <ShoppingCart size={16} /> {busy ? "Creating draft…" : "Create draft reorder"}
            </button>
            <button type="button" className="btn btn-secondary" onClick={onDetails}>
              View product
            </button>
          </div>
        </>
      )}
    </section>
  );
}
