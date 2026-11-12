"""Deterministic reconstructed inventory history.

Sales rows are treated as demand and are never updated. Fulfilled sales are the
portion that on-hand stock could cover. Receipts, returns, adjustments, and the
terminal reconciliation are marked SYNTHETIC_RECONSTRUCTED.

Closing stock = opening + receipts + returns + adjustments - fulfilled sales - write-offs.
The last snapshot day is reconciled to products.stock_on_hand at generation time.
Later operational receipts are not written back into these snapshots.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import numpy as np

PROVENANCE = "SYNTHETIC_RECONSTRUCTED"
VERSION = "v1"
SOURCE = "SYNTHETIC_RECONSTRUCTED"

_SNAP_SQL = """
INSERT INTO inventory_daily_snapshots(
  run_id, product_id, snapshot_date, opening_stock, received_units, sold_units,
  returned_units, adjustment_units, writeoff_units, unmet_demand_units, demand_units,
  closing_stock, unit_cost_paise, closing_value_paise, cogs_paise, revenue_paise, provenance
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

_LEDGER_SQL = """
INSERT INTO inventory_ledger(
  run_id, product_id, event_at, event_type, quantity_change, unit_cost_paise, reference, provenance
) VALUES (?,?,?,?,?,?,?,?)
"""

_RECEIPT_SQL = """
INSERT INTO inventory_receipts(
  run_id, product_id, supplier_id, ordered_date, promised_date, received_date,
  quantity, delay_days, on_time, kind, provenance
) VALUES (?,?,?,?,?,?,?,?,?,?,?)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summary(row: sqlite3.Row, *, reused: bool) -> dict:
    notes = {}
    try:
        notes = json.loads(row["notes"] or "{}")
    except json.JSONDecodeError:
        notes = {}
    return {
        "run_id": int(row["id"]),
        "status": row["status"],
        "reused": reused,
        "products": row["product_count"],
        "days": row["day_count"],
        "snapshot_date": row["snapshot_date"],
        "seed": int(row["seed"]),
        "provenance": SOURCE,
        "version": row["version"],
        "checksum": notes.get("checksum"),
        "reconciled_up": notes.get("reconciled_up"),
        "reconciled_down": notes.get("reconciled_down"),
        "reconciled_matched": notes.get("reconciled_matched"),
        "generated_at": row["generated_at"],
    }


def build_analytics(conn: sqlite3.Connection, *, seed: int = 42, force: bool = False) -> dict:
    """Create or reuse a reconstructed ledger and daily snapshots.

    Safe to rerun. Existing sales, stock, forecasts, and model rows are not modified.
    ``force`` replaces the run for this seed and snapshot date.
    """
    date_row = conn.execute("SELECT MIN(sale_date) AS a, MAX(sale_date) AS b, COUNT(*) AS n FROM sales").fetchone()
    if not date_row or not date_row["n"] or not date_row["b"]:
        raise ValueError("No sales rows are available to reconstruct inventory history")
    snapshot_date = str(date_row["b"])

    existing = conn.execute(
        """
        SELECT * FROM analytics_runs
        WHERE dataset_source=? AND seed=? AND snapshot_date=? AND version=?
        """,
        (SOURCE, int(seed), snapshot_date, VERSION),
    ).fetchone()
    if existing and existing["status"] == "complete" and not force:
        return _summary(existing, reused=True)

    products = conn.execute(
        """
        SELECT p.id, p.unit_cost_paise, p.selling_price_paise, p.stock_on_hand,
               p.reorder_point, p.pack_size, p.supplier_id,
               s.base_lead_days, s.delivery_reliability
        FROM products p
        JOIN suppliers s ON s.id = p.supplier_id
        WHERE p.is_active = 1
        ORDER BY p.id
        """
    ).fetchall()
    if not products:
        raise ValueError("No active products are available to reconstruct inventory history")

    demand: dict[int, dict[str, tuple[int, int]]] = {}
    dates: set[str] = set()
    for row in conn.execute(
        "SELECT product_id, sale_date, units, selling_price_paise FROM sales ORDER BY product_id, sale_date"
    ):
        pid = int(row["product_id"])
        demand.setdefault(pid, {})[str(row["sale_date"])] = (
            int(row["units"]),
            int(row["selling_price_paise"]),
        )
        dates.add(str(row["sale_date"]))
    calendar = sorted(dates)

    if existing:
        rid = int(existing["id"])
        conn.execute("DELETE FROM inventory_receipts WHERE run_id=?", (rid,))
        conn.execute("DELETE FROM inventory_ledger WHERE run_id=?", (rid,))
        conn.execute("DELETE FROM inventory_daily_snapshots WHERE run_id=?", (rid,))
        conn.execute("DELETE FROM analytics_runs WHERE id=?", (rid,))

    cur = conn.execute(
        """
        INSERT INTO analytics_runs(
          dataset_source, seed, snapshot_date, generated_at, version, status, product_count, day_count, notes
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (SOURCE, int(seed), snapshot_date, _now(), VERSION, "running", len(products), len(calendar), None),
    )
    run_id = int(cur.lastrowid)

    sum_closing = 0
    sum_sold = 0
    n_snap = 0
    n_ledger = 0
    reconciled_up = 0
    reconciled_down = 0
    reconciled_matched = 0
    snaps: list[tuple] = []
    ledgers: list[tuple] = []
    receipts: list[tuple] = []

    def flush() -> None:
        nonlocal snaps, ledgers, receipts
        if snaps:
            conn.executemany(_SNAP_SQL, snaps)
            snaps = []
        if ledgers:
            conn.executemany(_LEDGER_SQL, ledgers)
            ledgers = []
        if receipts:
            conn.executemany(_RECEIPT_SQL, receipts)
            receipts = []

    for product in products:
        pid = int(product["id"])
        cost = int(product["unit_cost_paise"])
        list_price = int(product["selling_price_paise"])
        target = int(product["stock_on_hand"])
        reorder = int(product["reorder_point"])
        pack = max(1, int(product["pack_size"]))
        supplier_id = int(product["supplier_id"])
        lead = max(1, int(product["base_lead_days"]))
        reliability = float(product["delivery_reliability"])
        series = demand.get(pid, {})
        units_only = [series.get(day, (0, list_price))[0] for day in calendar]
        mean_demand = (sum(units_only) / len(calendar)) if calendar else 0.0
        stock = max(reorder, int(round(mean_demand * (lead + 14))))
        rng = np.random.default_rng(int(seed) + pid * 1_000_003)
        pending: dict[str, list[dict]] = {}
        returns_next = 0
        ledgers.append((run_id, pid, f"{calendar[0]}T00:00:00", "opening", stock, cost, "OPENING", PROVENANCE))
        n_ledger += 1

        for i, day in enumerate(calendar):
            opening = stock
            day_receipts = pending.pop(day, [])
            received = sum(int(r["qty"]) for r in day_receipts)
            returned = returns_next
            returns_next = 0
            adjustment = 0
            if len(calendar) > 14 and i == (pid % len(calendar)):
                adjustment = 1 if float(rng.random()) < 0.5 else -1
                if opening + received + returned + adjustment < 0:
                    adjustment = 0
            available = opening + received + returned + adjustment
            dem, price = series.get(day, (0, list_price))
            sold = min(int(dem), available)
            unmet = int(dem) - sold
            routine_writeoff = 1 if i % 60 == (pid % 60) and (available - sold) > 25 else 0
            writeoff = routine_writeoff
            closing = available - sold - writeoff
            reconcile_writeoff = False

            if i == len(calendar) - 1:
                delta = target - closing
                if delta > 0:
                    received += delta
                    closing += delta
                    day_receipts.append(
                        {
                            "qty": delta,
                            "ordered": day,
                            "promised": day,
                            "delay": 0,
                            "on_time": 1,
                            "kind": "reconciliation",
                        }
                    )
                    reconciled_up += 1
                elif delta < 0:
                    writeoff += -delta
                    closing += delta
                    reconcile_writeoff = True
                    reconciled_down += 1
                else:
                    reconciled_matched += 1

            if closing < 0:
                raise RuntimeError(f"Negative stock for product {pid} on {day}")

            for rec in day_receipts:
                kind = rec.get("kind", "replenishment")
                ref = "RECONCILE_TO_SNAPSHOT" if kind == "reconciliation" else "SYNTHETIC_RECEIPT"
                ledgers.append(
                    (run_id, pid, f"{day}T08:00:00", "receipt", int(rec["qty"]), cost, ref, PROVENANCE)
                )
                n_ledger += 1
                receipts.append(
                    (
                        run_id,
                        pid,
                        supplier_id,
                        rec["ordered"],
                        rec["promised"],
                        day,
                        int(rec["qty"]),
                        int(rec["delay"]),
                        int(rec["on_time"]),
                        kind,
                        PROVENANCE,
                    )
                )
            if returned:
                ledgers.append((run_id, pid, f"{day}T09:00:00", "return", returned, cost, "SYNTHETIC_RETURN", PROVENANCE))
                n_ledger += 1
            if adjustment:
                ledgers.append(
                    (run_id, pid, f"{day}T10:00:00", "adjustment", adjustment, cost, "SYNTHETIC_ADJUSTMENT", PROVENANCE)
                )
                n_ledger += 1
            if sold:
                ledgers.append((run_id, pid, f"{day}T16:00:00", "sale", -sold, cost, "FULFILLED_SALE", PROVENANCE))
                n_ledger += 1
            if writeoff:
                ref = "RECONCILE_TO_SNAPSHOT" if reconcile_writeoff else "SYNTHETIC_WRITEOFF"
                ledgers.append((run_id, pid, f"{day}T18:00:00", "writeoff", -writeoff, cost, ref, PROVENANCE))
                n_ledger += 1

            snaps.append(
                (
                    run_id,
                    pid,
                    day,
                    opening,
                    received,
                    sold,
                    returned,
                    adjustment,
                    writeoff,
                    unmet,
                    int(dem),
                    closing,
                    cost,
                    closing * cost,
                    sold * cost,
                    sold * int(price),
                    PROVENANCE,
                )
            )
            n_snap += 1
            sum_closing += closing
            sum_sold += sold
            stock = closing

            if sold >= 8 and i + 1 < len(calendar) and float(rng.random()) < 0.05:
                returns_next = min(sold, max(1, int(round(sold * 0.04))))

            inbound_qty = sum(int(r["qty"]) for batch in pending.values() for r in batch)
            if stock + inbound_qty < reorder:
                cover = max(pack, int(round(mean_demand * (lead + 7))))
                need = cover - (stock + inbound_qty)
                if need > 0:
                    packs = (need + pack - 1) // pack
                    qty = max(pack, packs * pack)
                    delay = 0 if float(rng.random()) < reliability else int(rng.integers(1, 4))
                    arrival_idx = i + lead + delay
                    if arrival_idx < len(calendar):
                        pending.setdefault(calendar[arrival_idx], []).append(
                            {
                                "qty": qty,
                                "ordered": day,
                                "promised": calendar[i + lead],
                                "delay": delay,
                                "on_time": 1 if delay == 0 else 0,
                                "kind": "replenishment",
                            }
                        )

        flush()

    checksum = f"{sum_closing}:{sum_sold}:{n_snap}:{n_ledger}"
    notes = {
        "checksum": checksum,
        "method": (
            "Forward reconstruction from recorded demand. Receipts, returns, adjustments, "
            "and the snapshot-day receipt or write-off are SYNTHETIC_RECONSTRUCTED. "
            "The last closing balance is forced to products.stock_on_hand at generation time "
            "and is not rewritten when a later reorder is received."
        ),
        "reconciled_up": reconciled_up,
        "reconciled_down": reconciled_down,
        "reconciled_matched": reconciled_matched,
        "cost_model": "Fixed catalog unit_cost_paise. Revenue uses the sales-row price on fulfilled units only.",
        "supplier_performance": (
            "Receipt delay is drawn from supplier.delivery_reliability. "
            "On-time statistics from these rows are simulated, not observed carrier performance. "
            "Reconciliation receipts are excluded from that rate."
        ),
        "demand_vs_sales": "sales.units remain demand. sold_units are fulfilled. unmet_demand_units = demand - fulfilled.",
    }
    conn.execute(
        """
        UPDATE analytics_runs
        SET status='complete', generated_at=?, product_count=?, day_count=?, notes=?
        WHERE id=?
        """,
        (_now(), len(products), len(calendar), json.dumps(notes), run_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM analytics_runs WHERE id=?", (run_id,)).fetchone()
    assert row is not None
    return _summary(row, reused=False)
