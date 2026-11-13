import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  Area,
} from "recharts";
import { api, ApiError } from "../../api/client";
import { ChartCard } from "../../components/ChartCard";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { KpiCard } from "../../components/KpiCard";
import { SkeletonCard } from "../../components/Skeleton";
import { formatDate } from "../../utils/dates";
import { formatNumber, NOT_MEASURED } from "../../utils/format";
import type {
  RealDataBaselineRow,
  RealDataMetadata,
  RealDataMetrics,
  RealDataPredictionRow,
  RealDataSummary,
} from "../../types/api";

function pct(wape: number | null | undefined) {
  if (wape == null || Number.isNaN(wape)) return NOT_MEASURED;
  return `${(wape * 100).toFixed(2)}%`;
}

export function RealRetailPanel() {
  const [summary, setSummary] = useState<RealDataSummary | null>(null);
  const [metrics, setMetrics] = useState<RealDataMetrics | null>(null);
  const [baselines, setBaselines] = useState<RealDataBaselineRow[]>([]);
  const [meta, setMeta] = useState<RealDataMetadata | null>(null);
  const [products, setProducts] = useState<{ stock_code: string }[]>([]);
  const [sku, setSku] = useState<string>("");
  const [preds, setPreds] = useState<RealDataPredictionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [predError, setPredError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const s = await api.realDataSummary();
        if (cancelled) return;
        setSummary(s);
        setMeta(await api.realDataMetadata());
        if (!s.ready) {
          setLoading(false);
          return;
        }
        const [m, b, p] = await Promise.all([
          api.realDataMetrics(),
          api.realDataBaselines(),
          api.realDataProducts(100),
        ]);
        if (cancelled) return;
        setMetrics(m);
        setBaselines(b.rows ?? []);
        setProducts(p.products ?? []);
        const first = p.products?.[0]?.stock_code ?? "";
        setSku(first);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Failed to load real-data evaluation");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!sku || !summary?.ready) return;
    let cancelled = false;
    (async () => {
      setPredError(null);
      try {
        const res = await api.realDataPredictions({ stock_code: sku, limit: 60 });
        if (!cancelled) setPreds(res.rows ?? []);
      } catch (e) {
        if (!cancelled) {
          setPreds([]);
          setPredError(e instanceof Error ? e.message : "Predictions unavailable");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sku, summary?.ready]);

  const baselineChart = useMemo(
    () =>
      baselines.map((r) => ({
        name: r.method.replaceAll("_", " "),
        wape: r.wape ?? 0,
        isBest: metrics?.best_wape_method === r.method,
      })),
    [baselines, metrics?.best_wape_method],
  );

  const series = useMemo(
    () =>
      preds.map((r) => ({
        date: r.date,
        actual: r.actual_units,
        predicted: r.predicted_units,
        seasonal: r.seasonal_naive_units,
        p10: r.p10_units,
        p50: r.p50_units,
        p90: r.p90_units,
      })),
    [preds],
  );

  const scatter = useMemo(
    () => preds.map((r) => ({ actual: r.actual_units, predicted: r.predicted_units })),
    [preds],
  );

  if (loading && !summary) {
    return (
      <div className="grid-kpi-4">
        {[1, 2, 3, 4].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }
  if (error) return <ErrorState message={error} />;

  if (!summary?.ready) {
    return (
      <EmptyState
        title="Real retail evaluation not ready"
        message="Run python -m app.cli real-data-all --max-products 100 --seed 42 --threads 2 from backend/. Artifacts are isolated from the synthetic demo."
      />
    );
  }

  const cov = metrics?.interval?.empirical_coverage_p10_p90;

  return (
    <>
      <div className="note" style={{ marginBottom: 12 }}>
        Source label <strong>REAL_RETAIL_UCI</strong> · {summary.dataset_name} · {summary.currency} ·{" "}
        <a href={summary.source_url} target="_blank" rel="noreferrer">
          UCI archive
        </a>{" "}
        · {summary.license} · {summary.attribution}
      </div>

      <div className="grid-kpi-4">
        <KpiCard label="Holdout WAPE" value={pct(metrics?.ml?.wape)} sublabel="Pooled · lower better" />
        <KpiCard label="Holdout MAE" value={metrics?.ml?.mae != null ? formatNumber(metrics.ml.mae) : NOT_MEASURED} sublabel="Units / day" />
        <KpiCard label="Holdout RMSE" value={metrics?.ml?.rmse != null ? formatNumber(metrics.ml.rmse) : NOT_MEASURED} sublabel="Units / day" />
        <KpiCard
          label="Interval coverage"
          value={cov != null ? `${(cov * 100).toFixed(1)}%` : NOT_MEASURED}
          sublabel="Empirical p10–p90 (not 95% CI)"
        />
      </div>

      <div className="perf-grid">
        <ChartCard
          title="Actual vs predicted"
          subtitle={`SKU ${sku || "—"} · ${metrics?.evaluation_mode ?? "rolling_one_step_ahead"} · test period`}
        >
          {predError ? (
            <EmptyState title="No series" message={predError} />
          ) : series.length === 0 ? (
            <EmptyState title="No predictions" message="Select a SKU with test rows." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => formatDate(String(d)).slice(0, 6)} minTickGap={18} />
                <YAxis width={40} tick={{ fontSize: 10 }} />
                <Tooltip labelFormatter={(l) => formatDate(String(l))} />
                <Legend />
                <Area type="monotone" dataKey="p90" stroke="transparent" fill="var(--color-forecast)" fillOpacity={0.12} name="p90" />
                <Area type="monotone" dataKey="p10" stroke="transparent" fill="var(--color-bg)" fillOpacity={1} name="p10" />
                <Line type="monotone" dataKey="actual" stroke="var(--color-primary)" dot={false} strokeWidth={2} name="Actual" />
                <Line type="monotone" dataKey="predicted" stroke="var(--color-forecast)" strokeDasharray="4 3" dot={false} strokeWidth={2} name="Predicted" />
                <Line type="monotone" dataKey="seasonal" stroke="#8a6d3b" strokeDasharray="2 2" dot={false} name="Seasonal naive" />
              </ComposedChart>
            </ResponsiveContainer>
          )}
          <div style={{ marginTop: 10 }}>
            <label className="note" htmlFor="real-sku">
              SKU
            </label>
            <select
              id="real-sku"
              className="select"
              style={{ width: "auto", marginLeft: 8 }}
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              aria-label="Real retail SKU"
            >
              {products.map((p) => (
                <option key={p.stock_code} value={p.stock_code}>
                  {p.stock_code}
                </option>
              ))}
            </select>
          </div>
        </ChartCard>

        <ChartCard title="Model vs baselines" subtitle="Same test rows. Lower WAPE is better. Best method is highlighted by the measured numbers — not forced.">
          {baselineChart.length === 0 ? (
            <EmptyState title="No baselines" message="Evaluation reports are missing." />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={baselineChart} layout="vertical" margin={{ left: 8, right: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis type="number" tickFormatter={(v) => `${(Number(v) * 100).toFixed(0)}%`} />
                <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => (typeof v === "number" ? `${(v * 100).toFixed(2)}%` : String(v))} />
                <Bar dataKey="wape" name="WAPE" fill="#0b6b3a" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
          {metrics?.best_wape_method ? (
            <p className="note" style={{ marginTop: 8 }}>
              Lowest WAPE: {metrics.best_wape_method.replaceAll("_", " ")}
            </p>
          ) : null}
        </ChartCard>
      </div>

      <div className="perf-grid">
        <ChartCard title="Forecast uncertainty (selected SKU)" subtitle="p10 / p50 / p90 from quantile models on held-out days">
          {series.length === 0 ? (
            <EmptyState title="No interval series" message="Choose a SKU." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <ComposedChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => formatDate(String(d)).slice(0, 6)} minTickGap={18} />
                <YAxis width={40} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend />
                <Line dataKey="p10" stroke="#6b7280" dot={false} name="p10" />
                <Line dataKey="p50" stroke="var(--color-forecast)" dot={false} name="p50" />
                <Line dataKey="p90" stroke="#6b7280" dot={false} name="p90" />
                <Line dataKey="actual" stroke="var(--color-primary)" dot={false} name="Actual" />
              </ComposedChart>
            </ResponsiveContainer>
          )}
          <p className="note">
            Mean interval width (pooled):{" "}
            {metrics?.interval?.mean_interval_width != null ? formatNumber(metrics.interval.mean_interval_width) : NOT_MEASURED}
            {" · "}
            {metrics?.interval?.nominal_label ?? "p10–p90"}
          </p>
        </ChartCard>

        <ChartCard title="Error analysis" subtitle="Actual vs predicted scatter for the selected SKU (test days)">
          {scatter.length === 0 ? (
            <EmptyState title="No errors" message="No prediction rows." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis type="number" dataKey="actual" name="Actual" tick={{ fontSize: 10 }} />
                <YAxis type="number" dataKey="predicted" name="Predicted" tick={{ fontSize: 10 }} width={40} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={scatter} fill="#0b6b3a" name="Test points" />
              </ScatterChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      <section className="card">
        <h2 className="card-title">Dataset inspection · REAL_RETAIL_UCI</h2>
        <p className="card-sub">
          Distinct from <strong>SYNTHETIC_DEMO</strong>. Model version {metrics?.model_version ?? meta?.training?.model_version ?? "—"}.
          Selected SKUs: {summary.split_summary?.sku_selection?.n_selected ?? summary.status.selected_sku_count ?? "—"}.
        </p>
        <div className="stat-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12, marginTop: 12 }}>
          <div className="stat-tile">
            <div className="lbl">Train / val / test</div>
            <div className="val" style={{ fontSize: 14 }}>
              {summary.split_summary?.boundaries?.train_start ?? "?"} → {summary.split_summary?.boundaries?.train_end ?? "?"}
              <br />
              {summary.split_summary?.boundaries?.val_start ?? "?"} → {summary.split_summary?.boundaries?.val_end ?? "?"}
              <br />
              {summary.split_summary?.boundaries?.test_start ?? "?"} → {summary.split_summary?.boundaries?.test_end ?? "?"}
            </div>
          </div>
          <div className="stat-tile">
            <div className="lbl">Test rows / SKUs</div>
            <div className="val">
              {formatNumber(metrics?.n_test_rows ?? 0)} / {formatNumber(metrics?.n_skus ?? 0)}
            </div>
          </div>
          <div className="stat-tile">
            <div className="lbl">DOI / license</div>
            <div className="val" style={{ fontSize: 13 }}>
              <a href={summary.doi} target="_blank" rel="noreferrer">
                {summary.doi}
              </a>
              <br />
              {summary.license}
            </div>
          </div>
        </div>
        <p className="note" style={{ marginTop: 12 }}>
          Raw columns: {(meta?.raw_columns ?? []).join(", ") || "—"}. Daily schema: {(meta?.daily_sales_columns ?? []).join(", ") || "—"}.
        </p>
        <p className="note">
          Sample CSV downloads:{" "}
          <a href="/api/real-data/samples/raw.csv">raw_sample</a>
          {" · "}
          <a href="/api/real-data/samples/daily_sales.csv">daily_sales_sample</a>
          {" · "}
          <a href="/api/real-data/predictions/export.csv">test_predictions export</a>
        </p>
        {(summary.limitations?.length ?? 0) > 0 ? (
          <ul className="insight-list" style={{ marginTop: 10 }}>
            {summary.limitations!.slice(0, 6).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
      </section>
    </>
  );
}
