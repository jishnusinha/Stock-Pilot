import type { PredictiveFreshness, PredictiveOverview } from "../../types/api";

export function PredictionProvenance({
  forecastAsOf,
  modelVersion,
  freshness,
  operationalAsOf,
  intervalNote,
}: {
  forecastAsOf?: string | null;
  modelVersion?: string | null;
  freshness?: PredictiveFreshness | null;
  operationalAsOf?: string | null;
  intervalNote?: string | null;
}) {
  const status = freshness?.status ?? "unknown";
  const tone =
    status === "current" ? "badge-ok" : status === "unavailable" ? "badge-muted" : status === "stale" ? "badge-warn" : "badge-muted";

  return (
    <section className="card prediction-provenance" aria-label="Prediction provenance">
      <div className="card-head">
        <div>
          <h2 className="card-title">Forecast provenance</h2>
          <p className="card-sub">
            Predictions are anchored at forecast as-of from persisted agent outputs. Historical month filters only narrow the cohort — they do not move the forecast anchor.
          </p>
        </div>
        <span className={`badge freshness-badge ${tone}`} data-status={status}>
          {status === "unavailable" ? "Forecasts unavailable" : `Freshness: ${status}`}
        </span>
      </div>
      <div className="provenance-grid">
        <div>
          <span className="note">Forecast as-of</span>
          <strong>{forecastAsOf ?? "N/A"}</strong>
        </div>
        <div>
          <span className="note">Operational as-of</span>
          <strong>{operationalAsOf ?? "N/A"}</strong>
        </div>
        <div>
          <span className="note">Model version</span>
          <strong>{modelVersion ?? "N/A"}</strong>
        </div>
        {freshness?.stale_risk_count != null && freshness.stale_risk_count > 0 ? (
          <div>
            <span className="note">Stale risk rows</span>
            <strong>{freshness.stale_risk_count}</strong>
          </div>
        ) : null}
      </div>
      {intervalNote ? <p className="note">{intervalNote}</p> : null}
    </section>
  );
}

export function provenanceFromOverview(overview?: PredictiveOverview | null) {
  return {
    forecastAsOf: overview?.forecast_as_of,
    modelVersion: overview?.model_version,
    freshness: overview?.freshness,
    operationalAsOf: overview?.operational_as_of,
    intervalNote: overview?.interval_note,
  };
}
