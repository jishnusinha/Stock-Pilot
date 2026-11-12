import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { api } from "../api/client";
import { Badge } from "../components/Badge";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { useApi } from "../hooks/useApi";
import type { AgentCard, AgentRunSummary, AgentRunTrace } from "../types/api";
import { formatDateTime } from "../utils/dates";
import { formatLatencyMs, NOT_MEASURED } from "../utils/format";

const DAG_NODES = [
  { id: "data", label: "Synthetic sales", x: 40, y: 80 },
  { id: "demand", label: "Demand", x: 160, y: 40 },
  { id: "demand_interval", label: "Demand interval", x: 160, y: 100 },
  { id: "intermittence", label: "Intermittence", x: 160, y: 160 },
  { id: "price_response", label: "Price response", x: 280, y: 40 },
  { id: "calendar_effect", label: "Calendar", x: 280, y: 100 },
  { id: "sales_anomaly", label: "Anomaly", x: 280, y: 160 },
  { id: "product_similarity", label: "Similarity", x: 400, y: 70 },
  { id: "supplier_eta", label: "Supplier ETA", x: 400, y: 130 },
  { id: "stockout_risk", label: "Stockout risk", x: 520, y: 60 },
  { id: "excess_risk", label: "Excess risk", x: 520, y: 140 },
  { id: "optimizer", label: "Reorder optimizer", x: 640, y: 100 },
];

const DAG_EDGES: [string, string][] = [
  ["data", "demand"],
  ["data", "demand_interval"],
  ["data", "intermittence"],
  ["demand", "price_response"],
  ["demand", "calendar_effect"],
  ["demand_interval", "sales_anomaly"],
  ["intermittence", "product_similarity"],
  ["supplier_eta", "stockout_risk"],
  ["product_similarity", "excess_risk"],
  ["stockout_risk", "optimizer"],
  ["excess_risk", "optimizer"],
  ["demand", "optimizer"],
];

export function Agents() {
  const { data: agents, loading, error, offline, reload } = useApi((s) => api.agents(s), []);
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentCard | null>(null);
  const [trace, setTrace] = useState<AgentRunTrace | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [skuId, setSkuId] = useState(1);

  useEffect(() => {
    api.agentRuns({ page: 1, page_size: 20 }).then(setRuns).catch(() => setRuns([]));
  }, []);

  useEffect(() => {
    if (agents?.length && !selectedAgent) setSelectedAgent(agents[0]);
  }, [agents, selectedAgent]);

  async function loadTrace(traceId: string) {
    const t = await api.getTrace(traceId);
    setTrace(t);
  }

  async function triggerRun() {
    setTriggering(true);
    try {
      const t = await api.triggerRun({ product_id: skuId });
      setTrace(t);
      const list = await api.agentRuns();
      setRuns(list);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Trigger failed");
    } finally {
      setTriggering(false);
    }
  }

  const activeCount = agents?.filter((a) => a.artifact_available).length ?? 0;

  if (loading && !agents) {
    return <p>Loading agents…</p>;
  }

  if (error && !agents) {
    return <ErrorState message={error} onRetry={reload} offline={offline} />;
  }

  return (
    <>
      <header className="page-header">
        <h1>Agent Intelligence</h1>
        <p className="subtitle">Ten fitted ML agents + deterministic reorder optimizer (dependency DAG)</p>
      </header>

      <div className="grid-kpi-4">
        <KpiCard label="Fitted agents" value={`${activeCount} / 10`} sublabel="Active = artifact available" />
        <KpiCard label="Recent runs" value={String(runs.length)} />
        <KpiCard
          label="Last trace"
          value={runs[0] ? runs[0].trace_id.slice(0, 8) : "—"}
        />
        <KpiCard label="Orchestration" value="Deterministic" sublabel="No LLM messaging" />
      </div>

      <section className="card" style={{ marginBottom: 16, overflowX: "auto" }}>
        <h2 className="card-title">Pipeline DAG</h2>
        <svg width={720} height={200} role="img" aria-label="Agent dependency graph">
          {DAG_EDGES.map(([from, to]) => {
            const a = DAG_NODES.find((n) => n.id === from)!;
            const b = DAG_NODES.find((n) => n.id === to)!;
            return (
              <line
                key={`${from}-${to}`}
                x1={a.x + 50}
                y1={a.y + 16}
                x2={b.x}
                y2={b.y + 16}
                stroke="var(--color-border)"
                strokeWidth={2}
              />
            );
          })}
          {DAG_NODES.map((n) => (
            <g
              key={n.id}
              transform={`translate(${n.x},${n.y})`}
              style={{ cursor: n.id !== "data" && n.id !== "optimizer" ? "pointer" : "default" }}
              onClick={() => {
                const card = agents?.find((a) => a.id === n.id);
                if (card) setSelectedAgent(card);
              }}
            >
              <rect
                width={100}
                height={32}
                rx={8}
                fill={n.id === "optimizer" ? "var(--color-mint)" : "#fff"}
                stroke="var(--color-primary)"
                strokeWidth={1}
              />
              <text x={50} y={20} textAnchor="middle" fontSize={9} fill="var(--color-text)">
                {n.label}
              </text>
            </g>
          ))}
        </svg>
      </section>

      <div className="grid-2-1">
        <section className="card">
          <h2 className="card-title">Model agents</h2>
          <AgentGrid>
            {(agents ?? []).map((a) => (
              <AgentMiniCard
                key={a.id}
                agent={a}
                selected={selectedAgent?.id === a.id}
                onSelect={() => setSelectedAgent(a)}
              />
            ))}
          </AgentGrid>
          {(agents ?? []).length === 0 ? (
            <EmptyState title="No agent metadata" message="Train models via backend CLI." />
          ) : null}
        </section>

        <aside className="card">
          <h2 className="card-title">Inspector</h2>
          {selectedAgent ? (
            <Inspector agent={selectedAgent} />
          ) : (
            <p style={{ color: "var(--color-text-muted)" }}>Select an agent node or card.</p>
          )}
          <hr style={{ border: "none", borderTop: "1px solid var(--color-border)", margin: "16px 0" }} />
          <label style={{ fontSize: 13 }}>
            SKU for on-demand run
            <input
              className="input"
              type="number"
              min={1}
              value={skuId}
              onChange={(e) => setSkuId(Number(e.target.value))}
              style={{ marginTop: 8 }}
            />
          </label>
          <button
            type="button"
            className="btn btn-primary"
            style={{ marginTop: 12, width: "100%" }}
            disabled={triggering}
            onClick={() => triggerRun()}
          >
            <Play size={16} /> {triggering ? "Running…" : "Run decision"}
          </button>
        </aside>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        <h2 className="card-title">Recent runs</h2>
        {runs.length === 0 ? (
          <EmptyState title="No runs yet" message="Trigger an on-demand decision to create a trace." />
        ) : (
          <DataTable
            rows={runs}
            selectedId={trace?.trace_id}
            onSelect={(r) => loadTrace(r.trace_id).catch(alert)}
            columns={[
              { key: "id", header: "Trace", render: (r) => r.trace_id.slice(0, 12) },
              { key: "scenario", header: "Scenario", render: (r) => r.scenario ?? "—" },
              { key: "status", header: "Status", render: (r) => r.status },
              {
                key: "dur",
                header: "Duration",
                render: (r) => formatLatencyMs(r.duration_ms),
              },
              {
                key: "when",
                header: "Started",
                render: (r) => formatDateTime(r.started_at),
              },
            ]}
          />
        )}
      </section>

      {trace ? (
        <section className="card" style={{ marginTop: 16 }}>
          <h2 className="card-title">Trace {trace.trace_id}</h2>
          <ul style={{ fontSize: 13 }}>
            {trace.nodes.map((n) => (
              <li key={n.agent_id}>
                <strong>{n.name}</strong> — {n.status} ({formatLatencyMs(n.duration_ms)})
                {n.output_summary ? `: ${n.output_summary}` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

function AgentMiniCard({
  agent,
  selected,
  onSelect,
}: {
  agent: AgentCard;
  selected: boolean;
  onSelect: () => void;
}) {
  const statusLabel = agent.artifact_available ? "Active" : "Unavailable";
  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        textAlign: "left",
        padding: 12,
        borderRadius: 12,
        border: `1px solid ${selected ? "var(--color-primary)" : "var(--color-border)"}`,
        background: selected ? "var(--color-mint)" : "#fff",
        cursor: "pointer",
      }}
    >
      <div style={{ fontWeight: 600, fontSize: 13 }}>{agent.name}</div>
      <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>{agent.method ?? "—"}</div>
      <Badge variant={agent.artifact_available ? "mint" : "muted"}>{statusLabel}</Badge>
    </button>
  );
}

function Inspector({ agent }: { agent: AgentCard }) {
  const confidence =
    agent.confidence != null && !Number.isNaN(agent.confidence)
      ? `${(agent.confidence * 100).toFixed(1)}%`
      : NOT_MEASURED;
  return (
  <dl style={{ fontSize: 13, display: "grid", gridTemplateColumns: "auto 1fr", gap: "8px 12px" }}>
    <dt style={{ color: "var(--color-text-muted)" }}>Method</dt>
    <dd style={{ margin: 0 }}>{agent.method ?? "—"}</dd>
    <dt style={{ color: "var(--color-text-muted)" }}>Data source</dt>
    <dd style={{ margin: 0 }}>{agent.data_source ?? "SYNTHETIC_DEMO"}</dd>
    <dt style={{ color: "var(--color-text-muted)" }}>Confidence</dt>
    <dd style={{ margin: 0 }}>{confidence}</dd>
    <dt style={{ color: "var(--color-text-muted)" }}>Latency p95</dt>
    <dd style={{ margin: 0 }}>{formatLatencyMs(agent.latency_p95_ms)}</dd>
    <dt style={{ color: "var(--color-text-muted)" }}>Last run</dt>
    <dd style={{ margin: 0 }}>{agent.last_run_at ? formatDateTime(agent.last_run_at) : "—"}</dd>
    <dt style={{ color: "var(--color-text-muted)" }}>Output</dt>
    <dd style={{ margin: 0 }}>{agent.key_output ?? "—"}</dd>
  </dl>
  );
}

function AgentGrid({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
      {children}
    </div>
  );
}
