"""Persist agent run traces."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from app.agents.base import AgentResult
from app.db import repositories as repo


class TraceWriter:
    def __init__(self, conn: sqlite3.Connection, trace_id: str) -> None:
        self.conn = conn
        self.trace_id = trace_id
        self._starts: dict[str, float] = {}

    @contextmanager
    def span(self, agent_name: str) -> Iterator[None]:
        self._starts[agent_name] = time.perf_counter()
        try:
            yield
        finally:
            pass

    def record(self, result: AgentResult, input_summary: dict | None = None) -> None:
        started = self._starts.get(result.agent_name, time.perf_counter())
        repo.insert_agent_run(
            self.conn,
            {
                "trace_id": self.trace_id,
                "agent_name": result.agent_name,
                "started_at": repo.utc_now(),
                "duration_ms": result.duration_ms or (time.perf_counter() - started) * 1000,
                "status": result.status,
                "model_version": result.model_version,
                "provenance": result.provenance,
                "input_summary": input_summary or {},
                "output_summary": _summarize(result.output),
                "error_text": result.error,
            },
        )


def _summarize(output: dict[str, Any]) -> dict[str, Any]:
    slim = {}
    for k, v in output.items():
        if k in {"forecast_series", "daily_p50", "neighbors"}:
            slim[k] = f"{len(v)} items" if isinstance(v, list) else v
        else:
            slim[k] = v
    return slim
