import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { PageHeader } from "../components/Controls";
import { ErrorState } from "../components/ErrorState";
import { ProductDetailDrawer } from "../components/ProductDetailDrawer";
import { SkeletonCard } from "../components/Skeleton";
import { AnalyticsDataQualityPanel } from "../features/inventory-analytics/AnalyticsDataQualityPanel";
import { AnalyticsWorkspaceTabs } from "../features/inventory-analytics/AnalyticsWorkspaceTabs";
import { DecisionComparisonChart } from "../features/inventory-analytics/DecisionComparisonChart";
import { DemandOutlookChart } from "../features/inventory-analytics/DemandOutlookChart";
import { ExcessInventoryPanel } from "../features/inventory-analytics/ExcessInventoryPanel";
import { HistoricalAnalyticsPanel, type HistoricalBundle } from "../features/inventory-analytics/HistoricalAnalyticsPanel";
import { InventoryProjectionChart } from "../features/inventory-analytics/InventoryProjectionChart";
import { MLInsightPanel } from "../features/inventory-analytics/MLInsightPanel";
import { PredictionProvenance, provenanceFromOverview } from "../features/inventory-analytics/PredictionProvenance";
import { PredictiveErrorBoundary } from "../features/inventory-analytics/PredictiveErrorBoundary";
import { PredictiveKpiStrip } from "../features/inventory-analytics/PredictiveKpiStrip";
import { RecommendationExplorer } from "../features/inventory-analytics/RecommendationExplorer";
import { StockoutRiskPanel } from "../features/inventory-analytics/StockoutRiskPanel";
import { cohortParams, predictiveParams } from "../features/inventory-analytics/utils";
import type {
  AnalyticsFilters,
  PredictiveDataQuality,
  PredictiveDemand,
  PredictiveExplain,
  PredictiveOverview,
  PredictiveProjection,
  PredictiveRecommendations,
  PredictiveRisks,
  ProductDetail,
} from "../types/api";
import {
  analyticsFetchKey,
  clearAnalyticsQuery,
  predictiveFetchKey,
  readAnalyticsQuery,
  writeAnalyticsQuery,
  type AnalyticsQuery,
  type AnalyticsTab,
  type PredictiveHorizon,
  type ProjectionMode,
} from "../utils/analyticsQuery";

export function InventoryAnalytics() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const query = useMemo(() => readAnalyticsQuery(params), [params]);
  const tab = query.tab ?? "overview";
  const [bundle, setBundle] = useState<HistoricalBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [sectionError, setSectionError] = useState<string | null>(null);

  const [predictiveLoading, setPredictiveLoading] = useState(false);
  const [predictiveSectionError, setPredictiveSectionError] = useState<string | null>(null);
  const [predOverview, setPredOverview] = useState<PredictiveOverview | null>(null);
  const [predDemand, setPredDemand] = useState<PredictiveDemand | null>(null);
  const [predProjection, setPredProjection] = useState<PredictiveProjection | null>(null);
  const [predRisks, setPredRisks] = useState<PredictiveRisks | null>(null);
  const [predRecommendations, setPredRecommendations] = useState<PredictiveRecommendations | null>(null);
  const [predDataQuality, setPredDataQuality] = useState<PredictiveDataQuality | null>(null);
  const [predExplain, setPredExplain] = useState<PredictiveExplain | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainProductId, setExplainProductId] = useState<number | null>(null);

  const [drawerId, setDrawerId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchKey = analyticsFetchKey(query);
  const predKey = predictiveFetchKey(query);
  const predictiveRequestSeq = useRef(0);

  // Lightweight filter options — always available for the shared filter bar.
  useEffect(() => {
    const ac = new AbortController();
    api
      .analyticsFilters(ac.signal)
      .then((filters) => {
        setBundle((prev) =>
          prev
            ? { ...prev, filters }
            : {
                overview: { ready: false },
                months: [],
                turnover: [],
                movements: { ready: false },
                byValue: [],
                byQuantity: [],
                sales: [],
                categories: [],
                cells: [],
                abcProducts: [],
                slow: [],
                suppliers: [],
                filters,
              },
        );
      })
      .catch(() => undefined);
    return () => ac.abort();
  }, []);

  // Heavy historical analytics — only when Overview/Quality need them (avoids starving predictive APIs on 8GB hosts).
  useEffect(() => {
    if (tab !== "overview" && tab !== "quality") {
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    let active = true;
    setLoading(true);
    const q = cohortParams(query, { segment: undefined });
    const histQ = { ...q, segment: query.cell };
    Promise.allSettled([
      api.analyticsOverview(histQ, ac.signal),
      api.analyticsTrend(histQ, ac.signal),
      api.analyticsTurnover(histQ, ac.signal),
      api.analyticsMovements(histQ, ac.signal),
      api.analyticsTop(histQ, ac.signal),
      api.analyticsSales(histQ, ac.signal),
      api.analyticsCategories(histQ, ac.signal),
      api.analyticsAbc({ ...q, page_size: 200 }, ac.signal),
      api.analyticsSlow({ ...histQ, page_size: 50 }, ac.signal),
      api.analyticsSuppliers(histQ, ac.signal),
      api.analyticsFilters(ac.signal),
    ])
      .then((results) => {
        if (!active || ac.signal.aborted) return;
        const failed = results.filter((result) => result.status === "rejected");
        const overview = results[0].status === "fulfilled" ? results[0].value : null;
        if (!overview) {
          const reason = results[0].status === "rejected" ? results[0].reason : null;
          setOffline(reason instanceof TypeError);
          setError(reason instanceof Error ? reason.message : "Analytics request failed");
          return;
        }
        const trend = results[1].status === "fulfilled" ? results[1].value : null;
        const turnover = results[2].status === "fulfilled" ? results[2].value : null;
        const movements = results[3].status === "fulfilled" ? results[3].value : null;
        const top = results[4].status === "fulfilled" ? results[4].value : null;
        const sales = results[5].status === "fulfilled" ? results[5].value : null;
        const categories = results[6].status === "fulfilled" ? results[6].value : null;
        const abc = results[7].status === "fulfilled" ? results[7].value : null;
        const slow = results[8].status === "fulfilled" ? results[8].value : null;
        const suppliers = results[9].status === "fulfilled" ? results[9].value : null;
        const filters = results[10].status === "fulfilled" ? results[10].value : null;
        setBundle((prev) => ({
          overview,
          months: trend?.months ?? [],
          turnover: turnover?.months ?? [],
          turnoverDefinition: turnover?.definition,
          movements: movements ?? { ready: false },
          byValue: top?.by_value ?? [],
          byQuantity: top?.by_quantity ?? [],
          sales: sales?.months ?? [],
          categories: categories?.categories ?? [],
          cells: abc?.cells ?? [],
          abcProducts: abc?.products ?? [],
          abcRule: abc?.abc_rule,
          xyzRule: abc?.xyz_rule,
          slow: slow?.items ?? [],
          slowDefinition: slow?.definition,
          suppliers: suppliers?.items ?? [],
          supplierNote: suppliers?.simulated_label,
          catalogNote: suppliers?.catalog_reliability_label,
          filters: filters ?? prev?.filters ?? { ready: false, categories: [], suppliers: [], products: [], years: [], months: [] },
        }));
        setSectionError(failed.length ? "Some analytics sections could not be refreshed. The sections that loaded are still usable." : null);
        setError(null);
        setOffline(false);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      ac.abort();
    };
    // fetchKey + tab: historical payload only when descriptive tabs are active.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchKey, tab]);

  useEffect(() => {
    if (tab === "overview") {
      setPredictiveLoading(false);
      return;
    }
    const ac = new AbortController();
    const requestId = ++predictiveRequestSeq.current;
    setPredictiveLoading(true);
    const base = predictiveParams(query);
    const cohort = cohortParams(query);

    const isCurrent = () => requestId === predictiveRequestSeq.current;

    const run = async () => {
      if (tab === "quality") {
        const dq = await Promise.allSettled([api.predictiveDataQuality(cohort, ac.signal)]);
        if (!isCurrent()) return;
        setPredDataQuality(dq[0].status === "fulfilled" ? dq[0].value : null);
        setPredictiveSectionError(dq[0].status === "rejected" ? "Predictive data quality could not be refreshed. Historical overview data is unchanged." : null);
        return;
      }

      if (tab === "predictive") {
        const results = await Promise.allSettled([
          api.predictiveOverview(base, ac.signal),
          api.predictiveDemand(base, ac.signal),
          api.predictiveProjection(base, ac.signal),
          api.predictiveRisks(cohort, ac.signal),
        ]);
        if (!isCurrent()) return;
        const failed = results.filter((r) => r.status === "rejected");
        setPredOverview(results[0].status === "fulfilled" ? results[0].value : null);
        setPredDemand(results[1].status === "fulfilled" ? results[1].value : null);
        setPredProjection(results[2].status === "fulfilled" ? results[2].value : null);
        setPredRisks(results[3].status === "fulfilled" ? results[3].value : null);
        setPredictiveSectionError(failed.length ? "Some predictive sections could not be refreshed. Historical overview data is unchanged." : null);
        return;
      }

      if (tab === "decisions") {
        const results = await Promise.allSettled([
          api.predictiveOverview(base, ac.signal),
          api.predictiveRecommendations(cohort, ac.signal),
        ]);
        if (!isCurrent()) return;
        const failed = results.filter((r) => r.status === "rejected");
        setPredOverview(results[0].status === "fulfilled" ? results[0].value : null);
        setPredRecommendations(results[1].status === "fulfilled" ? results[1].value : null);
        setPredictiveSectionError(failed.length ? "Some predictive sections could not be refreshed. Historical overview data is unchanged." : null);
      }
    };

    run()
      .catch(() => {
        if (isCurrent()) setPredictiveSectionError("Predictive workspace request failed. Historical overview data is unchanged.");
      })
      .finally(() => {
        if (isCurrent()) setPredictiveLoading(false);
      });

    return () => {
      ac.abort();
    };
    // predKey + tab capture predictive refetch inputs without query object identity churn.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [predKey, tab]);

  useEffect(() => {
    const productId = explainProductId ?? (query.product ? Number(query.product) : null);
    if (tab !== "decisions" || productId == null || Number.isNaN(productId)) {
      if (tab !== "decisions") setPredExplain(null);
      return;
    }
    const ac = new AbortController();
    setExplainLoading(true);
    api
      .predictiveExplain(productId, ac.signal)
      .then((body) => {
        setPredExplain(body);
        setExplainLoading(false);
      })
      .catch(() => {
        if (!ac.signal.aborted) {
          setPredExplain(null);
          setExplainLoading(false);
        }
      });
    return () => ac.abort();
  }, [tab, explainProductId, query.product]);

  useEffect(() => {
    if (drawerId == null) {
      setDetail(null);
      return;
    }
    const ac = new AbortController();
    setDetailLoading(true);
    api
      .productDetail(drawerId, ac.signal)
      .then((product) => {
        setDetail(product);
        setDetailLoading(false);
      })
      .catch(() => {
        if (!ac.signal.aborted) setDetailLoading(false);
      });
    return () => ac.abort();
  }, [drawerId]);

  function update(partial: Partial<AnalyticsQuery>) {
    const next = { ...query, ...partial };
    setParams(writeAnalyticsQuery(next));
  }

  function setTab(next: AnalyticsTab) {
    update({ tab: next });
  }

  if (error && !bundle && tab === "overview") {
    return <ErrorState message={error} onRetry={() => setParams(params)} offline={offline} />;
  }

  const overview = bundle?.overview;
  const filters = bundle?.filters;
  const period =
    tab === "overview" || tab === "quality"
      ? overview?.period_start && overview?.period_end
        ? `${overview.period_start} to ${overview.period_end}`
        : "No snapshot days in this filter"
      : predOverview?.forecast_as_of
        ? `Forecast as-of ${predOverview.forecast_as_of}`
        : "Predictive as-of pending";

  const provenance = provenanceFromOverview(predOverview);
  const showHistoricalSkeleton = tab === "overview" && loading && !bundle;

  return (
    <>
      <PageHeader
        title="Inventory Analytics"
        subtitle="Understand inventory performance, predict future exposure, and explore smarter replenishment decisions."
        actions={<span className="badge badge-muted">{period}</span>}
      />

      <AnalyticsWorkspaceTabs value={tab} onChange={setTab} />

      <FilterBar query={query} filters={filters} onChange={update} onClear={() => setParams(writeAnalyticsQuery(clearAnalyticsQuery()))} />
      {loading && bundle ? <p className="note analytics-busy">Refreshing the selected view…</p> : null}
      {sectionError ? <p className="note section-error" role="status">{sectionError}</p> : null}
      {predictiveLoading && tab !== "overview" ? <p className="note analytics-busy">Refreshing predictive workspace…</p> : null}
      {predictiveSectionError ? <p className="note section-error" role="status">{predictiveSectionError}</p> : null}

      {showHistoricalSkeleton ? (
        <div className="grid-kpi-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : null}

      {tab === "overview" && bundle && overview ? (
        <HistoricalAnalyticsPanel bundle={bundle} query={query} update={update} onProductSelect={setDrawerId} />
      ) : null}

      {tab === "predictive" ? (
        <PredictiveErrorBoundary label="Predictive Intelligence">
          <PredictionProvenance {...provenance} />
          <PredictiveKpiStrip overview={predOverview} />
          <div className="analytics-split">
            <PredictiveErrorBoundary label="Demand outlook">
              <DemandOutlookChart
                data={predDemand}
                forecastAsOf={provenance.forecastAsOf}
                horizon={(query.horizon ?? "28") as PredictiveHorizon}
                onHorizonChange={(horizon) => update({ horizon })}
              />
            </PredictiveErrorBoundary>
            <PredictiveErrorBoundary label="Inventory projection">
              <InventoryProjectionChart
                data={predProjection}
                forecastAsOf={provenance.forecastAsOf}
                horizon={(query.horizon ?? "28") as PredictiveHorizon}
                mode={(query.mode ?? "no_reorder") as ProjectionMode}
                onHorizonChange={(horizon) => update({ horizon })}
                onModeChange={(mode) => update({ mode })}
              />
            </PredictiveErrorBoundary>
          </div>
          <PredictiveErrorBoundary label="Stockout risk">
            <StockoutRiskPanel data={predRisks} onSelectProduct={setDrawerId} />
          </PredictiveErrorBoundary>
          <PredictiveErrorBoundary label="Excess inventory">
            <ExcessInventoryPanel data={predRisks} onSelectProduct={setDrawerId} />
          </PredictiveErrorBoundary>
        </PredictiveErrorBoundary>
      ) : null}

      {tab === "decisions" ? (
        <>
          <PredictionProvenance {...provenance} />
          <RecommendationExplorer
            data={predRecommendations}
            onSelectProduct={setDrawerId}
            onExplain={(id) => setExplainProductId(id)}
          />
          <MLInsightPanel data={predRecommendations} />
          <DecisionComparisonChart explain={predExplain} loading={explainLoading} />
        </>
      ) : null}

      {tab === "quality" ? (
        <AnalyticsDataQualityPanel predictive={predDataQuality} historicalOverview={overview ?? null} />
      ) : null}

      {(drawerId != null || detailLoading) && (
        <ProductDetailDrawer
          product={detail}
          loading={detailLoading}
          tab="overview"
          onTab={() => undefined}
          onClose={() => setDrawerId(null)}
          onAdjust={() => navigate(`/inventory?product=${drawerId ?? ""}`)}
          onReorder={() => navigate(`/simulator?product=${drawerId ?? ""}`)}
          onExplain={() => {
            const trace = detail?.reorder_recommendation?.trace_id;
            if (trace) navigate(`/agents?trace=${encodeURIComponent(trace)}`);
          }}
        />
      )}
    </>
  );
}

function FilterBar({
  query,
  filters,
  onChange,
  onClear,
}: {
  query: AnalyticsQuery;
  filters?: AnalyticsFilters;
  onChange: (partial: Partial<AnalyticsQuery>) => void;
  onClear: () => void;
}) {
  const chips = [
    query.year ? { key: "year", label: query.year } : null,
    query.month ? { key: "month", label: `Month ${query.month}` } : null,
    query.category ? { key: "category", label: query.category } : null,
    query.supplier ? { key: "supplier", label: filters?.suppliers.find((row) => String(row.id) === query.supplier)?.name ?? "Supplier" } : null,
    query.product ? { key: "product", label: filters?.products.find((row) => String(row.id) === query.product)?.sku ?? "Product" } : null,
    query.cell ? { key: "cell", label: query.cell } : null,
  ].filter(Boolean) as { key: keyof AnalyticsQuery; label: string }[];

  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <div className="filter-bar">
        <select className="select" aria-label="Year" value={query.year ?? ""} onChange={(e) => onChange({ year: e.target.value || undefined })}>
          <option value="">All years</option>
          {(filters?.years ?? []).map((year) => (
            <option key={year} value={year}>{year}</option>
          ))}
        </select>
        <select className="select" aria-label="Month" value={query.month ?? ""} onChange={(e) => onChange({ month: e.target.value || undefined })}>
          <option value="">All months</option>
          {Array.from({ length: 12 }, (_, index) => (
            <option key={index + 1} value={index + 1}>{index + 1}</option>
          ))}
        </select>
        <select className="select" aria-label="Category" value={query.category ?? ""} onChange={(e) => onChange({ category: e.target.value || undefined })}>
          <option value="">All categories</option>
          {(filters?.categories ?? []).map((category) => (
            <option key={category} value={category}>{category}</option>
          ))}
        </select>
        <select className="select" aria-label="Supplier" value={query.supplier ?? ""} onChange={(e) => onChange({ supplier: e.target.value || undefined })}>
          <option value="">All suppliers</option>
          {(filters?.suppliers ?? []).map((supplier) => (
            <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
          ))}
        </select>
        <select className="select" aria-label="Product" value={query.product ?? ""} onChange={(e) => onChange({ product: e.target.value || undefined })}>
          <option value="">All products</option>
          {(filters?.products ?? []).map((product) => (
            <option key={product.id} value={product.id}>{product.sku} · {product.name}</option>
          ))}
        </select>
        <button type="button" className="btn btn-secondary" onClick={onClear}>Clear all</button>
      </div>
      <div className="chip-row">
        {chips.length === 0 ? <span className="note">No active filters. Charts use the full reconstructed history.</span> : null}
        {chips.map((chip) => (
          <button
            key={chip.key}
            type="button"
            className="chip"
            onClick={() => onChange({ [chip.key]: undefined })}
          >
            {chip.label} ×
          </button>
        ))}
      </div>
    </section>
  );
}
