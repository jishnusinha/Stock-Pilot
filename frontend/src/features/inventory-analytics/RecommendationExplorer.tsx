import { useNavigate } from "react-router-dom";
import { DataTable } from "../../components/DataTable";
import { EmptyState } from "../../components/EmptyState";
import type { PredictiveRecommendations } from "../../types/api";
import { formatNumber, formatPaise } from "../../utils/format";

export function RecommendationExplorer({
  data,
  onSelectProduct,
  onExplain,
}: {
  data: PredictiveRecommendations | null;
  onSelectProduct: (id: number) => void;
  onExplain: (id: number) => void;
}) {
  const navigate = useNavigate();

  if (!data?.ready) {
    return (
      <section className="card">
        <h2 className="card-title">Replenishment opportunities</h2>
        <EmptyState title="No recommendations" message={data?.note ?? "Optimizer has no open suggestions for this cohort."} />
      </section>
    );
  }

  return (
    <section className="card">
      <h2 className="card-title">Replenishment opportunities</h2>
      <p className="card-sub">{data.ranking_rule}</p>
      <p className="note">Total suggested spend {formatPaise(data.total_recommended_spend_paise ?? 0)} · forecast as-of {data.forecast_as_of ?? "—"}</p>
      <DataTable
        rows={data.items}
        onSelect={(row) => onSelectProduct(row.product_id)}
        columns={[
          { key: "product", header: "Product", render: (row) => `${row.name} · ${row.sku}` },
          { key: "qty", header: "Suggested qty", align: "right", render: (row) => formatNumber(row.suggested_qty) },
          { key: "cost", header: "Est. cost", align: "right", render: (row) => formatPaise(row.estimated_cost_paise) },
          {
            key: "risk",
            header: "Stockout risk",
            align: "right",
            render: (row) => (row.stockout_risk == null ? "N/A" : `${(row.stockout_risk * 100).toFixed(0)}%`),
          },
          { key: "arrival", header: "Predicted arrival", render: (row) => row.expected_arrival_date ?? "Unavailable" },
          {
            key: "actions",
            header: "",
            render: (row) => (
              <span className="chip-row">
                <button type="button" className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); navigate(`/simulator?product=${row.product_id}`); }}>
                  Simulator
                </button>
                {row.trace_id ? (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); navigate(`/agents?trace=${encodeURIComponent(row.trace_id!)}`); }}>
                    Agents
                  </button>
                ) : null}
                <button type="button" className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); onExplain(row.product_id); }}>
                  Explain
                </button>
              </span>
            ),
          },
        ]}
      />
      <p className="note explanation-col">Tap a row for product detail; explanations are deterministic text from persisted agent outputs.</p>
    </section>
  );
}
