"""Local in-process API latency sample.

Uses FastAPI's TestClient, so the numbers are application time on this machine.
They exclude browser network delay and are not a public production SLO.

Run from the backend directory:

    python scripts/benchmark_api.py
"""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.connection import connect
from app.main import app
from app.services.benchmark_stats import summarize_durations

WARMUP = 1
REPEATS = 8


def _endpoints(product_id: int) -> list[tuple[str, str]]:
    return [
        ("dashboard", "/api/dashboard"),
        ("inventory_summary", "/api/inventory/summary"),
        ("analytics_overview", "/api/analytics/overview"),
        ("analytics_trend", "/api/analytics/inventory-trend"),
        ("analytics_abc", "/api/analytics/abc-xyz"),
        ("product_detail", f"/api/products/{product_id}"),
        ("performance", "/api/performance"),
    ]


def main() -> int:
    settings.ensure_dirs()
    conn = connect()
    try:
        product = conn.execute("SELECT id FROM products WHERE is_active=1 ORDER BY id LIMIT 1").fetchone()
        sales = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    finally:
        conn.close()
    if product is None:
        raise SystemExit("No products are available to benchmark")
    product_id = int(product["id"])
    endpoints = _endpoints(product_id)
    results = []
    with TestClient(app) as client:
        for name, path in endpoints:
            for _ in range(WARMUP):
                client.get(path)
            samples: list[float] = []
            status = None
            nbytes = 0
            for _ in range(REPEATS):
                started = time.perf_counter()
                response = client.get(path)
                samples.append((time.perf_counter() - started) * 1000.0)
                status = response.status_code
                nbytes = len(response.content)
            summary = summarize_durations(samples)
            results.append(
                {
                    "name": name,
                    "path": path,
                    "status": status,
                    "payload_bytes": nbytes,
                    **summary,
                }
            )
    payload = {
        "method": "fastapi.TestClient in-process ASGI. Not a networked production measurement.",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "warmup_requests": WARMUP,
        "repeats": REPEATS,
        "threads": settings.threads,
        "python": platform.python_version(),
        "system": platform.platform(),
        "products": int(products),
        "sales_rows": int(sales),
        "database_bytes": Path(settings.db_path).stat().st_size if Path(settings.db_path).exists() else None,
        "endpoints": results,
    }
    out = settings.eval_dir / "api_benchmark.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
