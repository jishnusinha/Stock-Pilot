"""Refresh product risk cache + recommendations after risk-rule changes."""

from __future__ import annotations

from app.db import repositories as repo
from app.db.connection import connect
from app.services.orchestrator import run_decision


def main() -> None:
    conn = connect()
    ids = [
        int(r[0])
        for r in conn.execute(
            "SELECT id FROM products WHERE is_active=1 ORDER BY id"
        ).fetchall()
    ]
    conn.execute("DELETE FROM recommendations")
    conn.commit()
    ok = 0
    for i, pid in enumerate(ids):
        dec = run_decision(conn, pid, persist_trace=(i < 5))
        repo.insert_recommendation(
            conn,
            {
                "product_id": pid,
                "suggested_qty": dec["suggested_qty"],
                "expected_stockout_risk": dec["expected_stockout_risk"],
                "expected_excess_risk": dec["expected_excess_risk"],
                "estimated_cost_paise": dec["estimated_cost_paise"],
                "expected_arrival_date": dec["expected_arrival_date"],
                "explanation_json": dec["explanation"],
                "trace_id": dec["trace_id"],
            },
        )
        ok += 1
        if (i + 1) % 40 == 0:
            conn.commit()
            print("progress", i + 1)
    conn.commit()
    high = conn.execute(
        "SELECT COUNT(*) FROM product_risk_cache WHERE risk_level='high'"
    ).fetchone()[0]
    med = conn.execute(
        "SELECT COUNT(*) FROM product_risk_cache WHERE risk_level='medium'"
    ).fetchone()[0]
    nonzero = conn.execute(
        "SELECT COUNT(*) FROM recommendations WHERE suggested_qty>0"
    ).fetchone()[0]
    print("done", ok, "high", high, "medium", med, "nonzero_recs", nonzero)
    conn.close()


if __name__ == "__main__":
    main()
