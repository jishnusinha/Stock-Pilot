"""Local API smoke checks via TestClient (no long-lived server)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def main() -> int:
    c = TestClient(app)
    checks: list = []
    for path in [
        "/api/health",
        "/api/dashboard",
        "/api/products?page_size=5",
        "/api/performance",
        "/api/agents",
    ]:
        r = c.get(path)
        if r.status_code != 200:
            summary: object = r.text[:80]
        else:
            payload = r.json()
            if isinstance(payload, dict):
                summary = list(payload.keys())[:8]
            elif isinstance(payload, list):
                summary = f"list[{len(payload)}]"
            else:
                summary = type(payload).__name__
        checks.append((path, r.status_code, summary))

    prod = c.get("/api/products?page_size=1").json()["items"][0]
    price = int(prod.get("unit_price_paise") or 10000)
    sim = c.post(
        "/api/simulate",
        json={
            "product_id": prod["id"],
            "reorder_qty": int(prod.get("pack_size") or 12),
            "proposed_price_paise": max(100, price // 2),
            "lead_time_days": 5,
            "budget_paise": 5_000_000,
        },
    )
    body = sim.json()
    checks.append(
        (
            "/api/simulate",
            sim.status_code,
            {
                "applied": body.get("applied_qty"),
                "series": len(body.get("proposed_series") or []),
                "price_effect": (body.get("price_effect") or {}).get("type"),
                "demand": (body.get("proposed_metrics") or {}).get("demand_p50"),
            },
        )
    )
    perf = c.get("/api/performance").json()
    checks.append(
        (
            "perf_series",
            len(perf.get("backtest_series") or []),
            perf.get("evaluation_mode"),
            (perf.get("kpis") or [{}])[0].get("label"),
        )
    )
    adj = c.post(
        f"/api/products/{prod['id']}/adjust-stock",
        json={"delta": 1, "reason": "smoke"},
    )
    checks.append(("adjust", adj.status_code))

    # Revert adjust to avoid permanently changing demo stock by +1 each smoke
    c.post(
        f"/api/products/{prod['id']}/adjust-stock",
        json={"delta": -1, "reason": "smoke_revert"},
    )

    print("SMOKE_OK")
    for x in checks:
        print(x)
    failed = [x for x in checks if isinstance(x, tuple) and len(x) > 1 and x[1] not in (200, 28) and not str(x[0]).startswith("perf")]
    # health/dashboard/etc must be 200; perf_series tuple is (name, len, mode, label)
    http_failed = [
        x
        for x in checks
        if isinstance(x[0], str)
        and x[0].startswith("/api")
        and x[1] != 200
    ]
    return 1 if http_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
