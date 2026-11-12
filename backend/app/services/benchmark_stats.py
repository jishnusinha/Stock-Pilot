"""Percentile summaries for local latency samples.

Uses the nearest-rank method: the smallest sample whose rank is at least
ceil(p/100 * n). This is a local measurement helper, not a production SLO.
"""

from __future__ import annotations

import math


def summarize_durations(samples_ms: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(float(value) for value in samples_ms)
    if not ordered:
        return {"n": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}

    def percentile(percent: float) -> float:
        rank = max(1, math.ceil((percent / 100.0) * len(ordered)))
        return ordered[rank - 1]

    return {
        "n": len(ordered),
        "p50_ms": percentile(50),
        "p95_ms": percentile(95),
        "max_ms": ordered[-1],
    }
