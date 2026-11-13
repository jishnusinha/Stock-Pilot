import type { AnalyticsOverview, PredictiveDataQuality } from "../../types/api";
import { HistoricalQualityPanel } from "./HistoricalQualityPanel";

export function AnalyticsDataQualityPanel({
  predictive,
  historicalOverview,
}: {
  predictive: PredictiveDataQuality | null;
  historicalOverview?: AnalyticsOverview | null;
}) {
  return (
    <>
      <section className="card quality-panel predictive-quality" aria-label="Predictive data quality">
        <div className="card-head">
          <div>
            <h2 className="card-title">Predictive model lineage</h2>
            <p className="card-sub">Persisted forecasts and agent versions. Endpoints do not retrain on GET.</p>
          </div>
          <span className="badge badge-muted">{predictive?.freshness?.status ?? "unknown"}</span>
        </div>
        {predictive?.forecast_coverage ? (
          <p className="note">
            Forecast coverage {predictive.forecast_coverage.covered ?? 0} / {predictive.forecast_coverage.selected ?? 0} SKUs
          </p>
        ) : null}
        {(predictive?.stale_risk_count ?? predictive?.freshness?.stale_risk_count ?? 0) > 0 ? (
          <p className="note section-error" role="status">
            {predictive?.stale_risk_count ?? predictive?.freshness?.stale_risk_count} SKU risk rows may be stale after stock changes.
          </p>
        ) : null}
        <div className="quality-grid">
          {(predictive?.model_versions ?? []).map((row) => (
            <div key={row.agent_name}>
              <span className="note">{row.agent_name}</span>
              <strong>{row.version ?? "N/A"}</strong>
              <span className="note">{row.trained_at ?? ""}</span>
            </div>
          ))}
        </div>
        <ul className="insight-list">
          {(predictive?.limitations ?? []).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {predictive?.interval_note ? <p className="note">{predictive.interval_note}</p> : null}
        {predictive?.projection_note ? <p className="note">{predictive.projection_note}</p> : null}
      </section>
      {historicalOverview ? <HistoricalQualityPanel overview={historicalOverview} /> : null}
    </>
  );
}
