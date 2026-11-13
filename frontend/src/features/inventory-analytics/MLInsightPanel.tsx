import type { PredictiveRecommendations } from "../../types/api";

export function MLInsightPanel({ data }: { data: PredictiveRecommendations | null }) {
  const insights = data?.insights ?? [];
  if (!insights.length) return null;

  return (
    <section className="card ml-insight-panel">
      <h2 className="card-title">ML insights</h2>
      <p className="card-sub">Deterministic portfolio notes from recommendation ranking — not opaque scores.</p>
      <ul className="insight-list">
        {insights.map((row) => (
          <li key={row.id} data-severity={row.severity}>
            {row.title ? <strong>{row.title}: </strong> : null}
            {row.text}
          </li>
        ))}
      </ul>
    </section>
  );
}
