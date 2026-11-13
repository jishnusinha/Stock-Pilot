import type { AnalyticsOverview } from "../../types/api";
import { formatNumber, formatPaise } from "../../utils/format";

export function HistoricalQualityPanel({ overview }: { overview: AnalyticsOverview }) {
  const recon = overview.reconciliation;
  const fingerprint = (overview.source_fingerprint || "").slice(0, 12);
  return (
    <section className="card quality-panel" aria-label="Reconstruction quality">
      <div className="card-head">
        <div>
          <h2 className="card-title">Reconstruction quality</h2>
          <p className="card-sub">Synthetic reconstructed history. Terminal reconciliation is separate from simulated replenishment.</p>
        </div>
        <span className="badge badge-muted">Synthetic data</span>
      </div>
      <div className="quality-grid">
        <div><span className="note">Run</span><strong>{overview.run_id ?? "N/A"}</strong></div>
        <div><span className="note">Freshness</span><strong>{overview.freshness ?? "N/A"}</strong></div>
        <div><span className="note">Fingerprint</span><strong className="tabular">{fingerprint || "N/A"}</strong></div>
        <div><span className="note">Algorithm</span><strong>{overview.algorithm_version ?? "v1"}</strong></div>
        <div><span className="note">Reconciled up</span><strong>{recon ? `${formatNumber(recon.products_up)} SKUs · ${formatPaise(recon.up_value_paise)}` : "N/A"}</strong></div>
        <div><span className="note">Reconciled down</span><strong>{recon ? `${formatNumber(recon.products_down)} SKUs · ${formatPaise(recon.down_value_paise)}` : "N/A"}</strong></div>
        <div><span className="note">No adjustment</span><strong>{recon ? formatNumber(recon.products_matched) : "N/A"}</strong></div>
        <div><span className="note">Absolute impact</span><strong>{recon ? formatPaise(recon.absolute_value_paise) : "N/A"}</strong></div>
      </div>
      <p className="note">{recon?.explanation || overview.reconciliation_note}</p>
      {overview.anchor_note ? <p className="note">{overview.anchor_note}</p> : null}
    </section>
  );
}
