import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Play } from "lucide-react";
import { api } from "../api/client";
import { AgentGraph, useGraphStatuses } from "../components/AgentGraph";
import { StatusBadge } from "../components/Badge";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KpiCard } from "../components/KpiCard";
import { PageHeader } from "../components/Controls";
import { SkeletonCard } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { useApi } from "../hooks/useApi";
import { AGENT_COPY, type AgentId } from "../data/orchestration";
import type { AgentCard, AgentRunSummary, AgentRunTrace } from "../types/api";
import { formatDateTime } from "../utils/dates";
import { formatLatencyMs, NOT_MEASURED } from "../utils/format";

export function Agents() {
  const toast = useToast();
  const [params] = useSearchParams();
  const traceParam = params.get("trace");
  const { data: agents, loading, error, offline, reload } = useApi((s) => api.agents(s), []);
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("demand");
  const [trace, setTrace] = useState<AgentRunTrace | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [productId, setProductId] = useState(1);
  const statuses = useGraphStatuses(agents);

  useEffect(() => {
    api.agentRuns({ page: 1, page_size: 20 }).then(setRuns).catch(() => setRuns([]));
  }, []);

  useEffect(() => {
    if (!traceParam) return;
    let cancelled = false;
    api
      .getTrace(traceParam)
      .then((next) => {
        if (!cancelled) setTrace(next);
      })
      .catch((e: unknown) => {
        if (!cancelled) toast.error(e instanceof Error ? e.message : "Could not load trace");
      });
    return () => {
      cancelled = true;
    };
  }, [traceParam, toast]);

  const selectedAgent = agents?.find((a) => a.id === selectedId) ?? null;
  const traceNode = trace?.nodes.find((n) => n.agent_id === selectedId);
  const highlighted = useMemo(() => new Set(trace?.nodes.map((n) => n.agent_id) ?? []), [trace]);
  const activeCount = agents?.filter((a) => a.artifact_available).length ?? 0;
  const last = runs[0];

  async function loadTrace(traceId: string) {
    try {
      setTrace(await api.getTrace(traceId));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load trace");
    }
  }

  async function triggerRun() {
    setTriggering(true);
    try {
      const next = await api.triggerRun({ product_id: productId });
      setTrace(next);
      setRuns(await api.agentRuns());
      toast.success(`Decision finished in ${formatLatencyMs(next.total_duration_ms)}.`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Trigger failed");
    } finally {
      setTriggering(false);
    }
  }

  if (loading && !agents) {
    return (
      <>
        <PageHeader title="Agent Intelligence" subtitle="Loading model registry…" />
        <div className="grid-kpi-4">
          {[1, 2, 3, 4].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </>
    );
  }

  if (error && !agents) return <ErrorState message={error} onRetry={reload} offline={offline} />;

  return (
    <>
      <PageHeader
        title="Agent Intelligence"
        subtitle="Ten fitted models plus a deterministic optimizer. Edges are the orchestrator’s real inputs, not a decorative diagram."
      />

      <div className="grid-kpi-4">
        <KpiCard label="Trained agents" value={`${activeCount} / 10`} sublabel="Artifact present on disk" />
        <KpiCard label="Recent runs" value={String(runs.length)} sublabel="Loaded execution traces" />
        <KpiCard label="Last status" value={last?.status ?? "—"} sublabel={last ? last.trace_id.slice(0, 10) : "No trace yet"} />
        <KpiCard
          label="Last duration"
          value={last?.duration_ms != null ? formatLatencyMs(last.duration_ms) : NOT_MEASURED}
          sublabel="Measured for that run"
        />
      </div>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <div>
            <h2 className="card-title">Execution graph</h2>
            <p className="card-sub">Select a node to inspect it. A loaded trace outlines the agents that actually ran.</p>
          </div>
        </div>
        <AgentGraph
          selectedId={selectedId}
          onSelect={setSelectedId}
          statuses={statuses}
          highlighted={trace ? highlighted : null}
        />
      </section>

      <div className="agents-layout">
        <section className="card">
          <div className="card-head">
            <div>
              <h2 className="card-title">Execution traces</h2>
              <p className="card-sub">Select a run to see sequence, status, and duration.</p>
            </div>
          </div>
          {runs.length === 0 ? (
            <EmptyState title="No runs yet" message="Trigger a decision for a product id to record a trace." />
          ) : (
            <DataTable
              rows={runs}
              selectedId={trace?.trace_id}
              onSelect={(r) => void loadTrace(r.trace_id)}
              columns={[
                { key: "id", header: "Trace", render: (r) => r.trace_id.slice(0, 12) },
                { key: "scenario", header: "Trigger", render: (r) => r.scenario ?? "—" },
                { key: "agents", header: "Agents", render: (r) => String(r.agents?.length ?? 0) },
                { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
                { key: "dur", header: "Duration", render: (r) => formatLatencyMs(r.duration_ms) },
                { key: "when", header: "Started", render: (r) => formatDateTime(r.started_at) },
              ]}
            />
          )}
          {trace ? <Waterfall trace={trace} onPick={setSelectedId} /> : <p className="note">Open a trace to see the waterfall.</p>}
        </section>

        <aside className="stack">
          <Inspector agent={selectedAgent} copyId={selectedId} node={traceNode} trace={trace} />
          <section className="card">
            <h2 className="card-title">Run a decision</h2>
            <p className="card-sub">On-demand orchestration for one product. This writes a trace; it does not place a supplier order.</p>
            <label className="field" style={{ marginTop: 12 }}>
              Product id
              <input className="input" type="number" min={1} value={productId} onChange={(e) => setProductId(Number(e.target.value))} />
            </label>
            <button type="button" className="btn btn-primary" style={{ width: "100%" }} disabled={triggering || productId < 1} onClick={() => void triggerRun()}>
              <Play size={16} /> {triggering ? "Running…" : "Run decision"}
            </button>
          </section>
        </aside>
      </div>
    </>
  );
}

function Inspector({
  agent,
  copyId,
  node,
  trace,
}: {
  agent: AgentCard | null;
  copyId: string;
  node?: AgentRunTrace["nodes"][number];
  trace: AgentRunTrace | null;
}) {
  const copy = AGENT_COPY[copyId as AgentId];
  return (
    <section className="card">
      <h2 className="card-title">{copy?.title ?? agent?.name ?? copyId}</h2>
      <p className="note" style={{ marginTop: 0 }}>{copy?.purpose ?? "No description for this id."}</p>
      <dl className="stat-grid" style={{ gridTemplateColumns: "1fr" }}>
        <Info label="Algorithm" value={agent?.method && agent.method !== agent.id ? agent.method : copy?.algorithm ?? "—"} />
        <Info label="Provenance" value={agent?.data_source ?? (copyId === "optimizer" ? "Deterministic" : "—")} />
        <Info label="Inputs" value={copy?.inputs ?? "—"} />
        <Info label="Outputs" value={copy?.outputs ?? agent?.key_output ?? "—"} />
        <Info label="Artifact" value={copyId === "optimizer" ? "Not a fitted model" : agent ? (agent.artifact_available ? "Available" : "Missing") : "—"} />
        <Info label="Median latency" value={formatLatencyMs(agent?.latency_median_ms)} />
        <Info label="p95 latency" value={formatLatencyMs(agent?.latency_p95_ms)} />
        <Info label="Last run" value={agent?.last_run_at ? formatDateTime(agent.last_run_at) : "—"} />
        <Info label="Selected trace" value={trace ? `${trace.trace_id.slice(0, 12)} · ${formatLatencyMs(trace.total_duration_ms)}` : "None"} />
        <Info label="This step" value={node ? `${node.status} · ${formatLatencyMs(node.duration_ms)}` : copyId === "optimizer" ? "Not timed separately" : "Not in the selected trace"} />
      </dl>
      {node?.output_summary ? (
        <p className="note">Output summary: {node.output_summary}</p>
      ) : null}
      {agent?.confidence != null ? (
        <p className="note">Reported confidence: {(agent.confidence * 100).toFixed(1)}%</p>
      ) : (
        <p className="note">Confidence is not measured for this agent.</p>
      )}
    </section>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-tile">
      <div className="lbl">{label}</div>
      <div className="val" style={{ fontSize: 13, fontWeight: 600 }}>{value}</div>
    </div>
  );
}

function Waterfall({ trace, onPick }: { trace: AgentRunTrace; onPick: (id: string) => void }) {
  const max = Math.max(1, ...trace.nodes.map((n) => n.duration_ms ?? 0));
  return (
    <div style={{ marginTop: 16 }}>
      <h3 className="card-title">Trace waterfall</h3>
      <p className="card-sub">Bar length is this step’s measured duration relative to the slowest step in the trace.</p>
      <div style={{ marginTop: 10 }}>
        {trace.nodes.map((node) => (
          <button
            key={`${node.agent_id}-${node.name}`}
            type="button"
            className="waterfall-row"
            onClick={() => onPick(node.agent_id)}
            style={{ width: "100%", background: "transparent", border: 0, textAlign: "left", cursor: "pointer" }}
          >
            <span>{node.name}</span>
            <span className="waterfall-bar" aria-hidden>
              <span style={{ width: `${((node.duration_ms ?? 0) / max) * 100}%` }} />
            </span>
            <span className="tabular">{formatLatencyMs(node.duration_ms)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
