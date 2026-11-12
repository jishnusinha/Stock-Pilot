import { useEffect, useId, useMemo, useState } from "react";
import { AGENT_COPY, ORCH_COLUMNS, ORCH_EDGES, edgeOnPath, dependencyPath, type AgentId } from "../data/orchestration";

const NODE_W = 156;
const NODE_H = 52;
const COL_GAP = 46;
const ROW_GAP = 8;
const PAD_X = 16;
const PAD_Y = 36;

type Status = "active" | "ready" | "unavailable" | "ok" | "error" | string;

export function AgentGraph({
  selectedId,
  onSelect,
  statuses,
  highlighted,
}: {
  selectedId?: string | null;
  onSelect: (id: string) => void;
  statuses?: Record<string, Status>;
  highlighted?: Set<string> | null;
}) {
  const [scale, setScale] = useState(1);
  const titleId = useId();
  const positions = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    ORCH_COLUMNS.forEach((col, ci) => {
      col.ids.forEach((id, ri) => {
        map.set(id, {
          x: PAD_X + ci * (NODE_W + COL_GAP),
          y: PAD_Y + ri * (NODE_H + ROW_GAP),
        });
      });
    });
    return map;
  }, []);

  const width = PAD_X * 2 + ORCH_COLUMNS.length * NODE_W + (ORCH_COLUMNS.length - 1) * COL_GAP;
  const height =
    PAD_Y +
    12 +
    Math.max(...ORCH_COLUMNS.map((c) => c.ids.length)) * (NODE_H + ROW_GAP);

  const path = selectedId ? dependencyPath(selectedId) : null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
        <p className="card-sub" id={titleId}>
          Directed edges follow the orchestrator: upstream signals condition demand; risks score each candidate order; the optimizer is deterministic.
        </p>
        <div className="seg" role="group" aria-label="Graph zoom">
          <button type="button" onClick={() => setScale((s) => Math.max(0.7, Number((s - 0.1).toFixed(2))))} aria-label="Zoom out">
            −
          </button>
          <button type="button" onClick={() => setScale(1)}>
            {Math.round(scale * 100)}%
          </button>
          <button type="button" onClick={() => setScale((s) => Math.min(1.3, Number((s + 0.1).toFixed(2))))} aria-label="Zoom in">
            +
          </button>
        </div>
      </div>
      <div className="graph-scroll">
        <svg
          width={width * scale}
          height={height * scale}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-labelledby={titleId}
        >
          {ORCH_COLUMNS.map((col, ci) => (
            <text
              key={col.title}
              x={PAD_X + ci * (NODE_W + COL_GAP)}
              y={18}
              fontSize={11}
              fill="#5f6d65"
              fontWeight={600}
            >
              {col.title}
            </text>
          ))}
          {ORCH_EDGES.map(([from, to]) => {
            const a = positions.get(from);
            const b = positions.get(to);
            if (!a || !b) return null;
            const x1 = a.x + NODE_W;
            const y1 = a.y + NODE_H / 2;
            const x2 = b.x;
            const y2 = b.y + NODE_H / 2;
            const mid = (x1 + x2) / 2;
            const active = selectedId ? edgeOnPath(from, to, selectedId) : false;
            return (
              <path
                key={`${from}-${to}`}
                d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke={active ? "#0b6b3a" : "#c5cdc6"}
                strokeWidth={active ? 2.25 : 1.25}
                markerEnd="url(#arrow)"
              />
            );
          })}
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" fill="#8aa092" />
            </marker>
          </defs>
          {[...positions.entries()].map(([id, pos]) => {
            const copy = AGENT_COPY[id as AgentId];
            const selected = selectedId === id;
            const onPath = path?.has(id) && !selected;
            const traced = highlighted?.has(id);
            const status = statuses?.[id];
            return (
              <g
                key={id}
                className={`agent-node${selected ? " selected" : ""}${onPath ? " on-path" : ""}${id === "optimizer" ? " optimizer" : ""}`}
                transform={`translate(${pos.x},${pos.y})`}
                onClick={() => onSelect(id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(id);
                  }
                }}
                tabIndex={0}
                role="button"
                aria-pressed={selected}
                aria-label={copy?.title ?? id}
              >
                <rect width={NODE_W} height={NODE_H} rx={12} />
                <text x={12} y={22} fontSize={12} fontWeight={650} fill="#1b2520">
                  {copy?.title ?? id}
                </text>
                <text x={12} y={40} fontSize={10} fill="#5f6d65">
                  {statusLabel(id, status, traced)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

function statusLabel(id: string, status: Status | undefined, traced?: boolean) {
  if (id === "optimizer") return traced ? "In decision path" : "Deterministic";
  if (traced) return "In selected trace";
  if (!status) return "Select to inspect";
  if (status === "active" || status === "ok" || status === "ready") return "Artifact ready";
  if (status === "unavailable" || status === "error") return "Unavailable";
  return String(status);
}

export function useGraphStatuses(agents: { id: string; status: string; artifact_available: boolean }[] | null) {
  const [map, setMap] = useState<Record<string, Status>>({});
  useEffect(() => {
    const next: Record<string, Status> = { optimizer: "ready" };
    for (const agent of agents ?? []) {
      next[agent.id] = agent.artifact_available ? "active" : "unavailable";
    }
    setMap(next);
  }, [agents]);
  return map;
}
