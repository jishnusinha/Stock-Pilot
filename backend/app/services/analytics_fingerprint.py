"""Deterministic fingerprints for reconstructed inventory history.

The source fingerprint hashes the inputs the reconstruction actually reads.
Live on-hand stock is not part of that hash. The anchor fingerprint freezes
the stock quantities used when a run is built, so a later receipt can change
operational stock without looking like a historical source change.
"""

from __future__ import annotations

import hashlib
import sqlite3

ALGORITHM_VERSION = "v1"

_CACHE: dict[tuple, str] = {}


def _canon(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.8f}"
    return str(value)


def _consume(hasher: hashlib._Hash, conn: sqlite3.Connection, label: str, sql: str, params: tuple = ()) -> None:
    hasher.update(f"[{label}]\n".encode("utf-8"))
    for row in conn.execute(sql, params):
        hasher.update("|".join(_canon(value) for value in tuple(row)).encode("utf-8"))
        hasher.update(b"\n")


def _stamp(conn: sqlite3.Connection, seed: int, snapshot_date: str) -> tuple:
    row = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM sales),
          (SELECT COALESCE(SUM(units), 0) FROM sales),
          (SELECT COALESCE(SUM(product_id * units), 0) FROM sales),
          (SELECT COALESCE(SUM(selling_price_paise), 0) FROM sales),
          (SELECT COALESCE(MAX(id), 0) FROM sales),
          (SELECT COALESCE(SUM(unit_cost_paise * id), 0) FROM products),
          (SELECT COALESCE(SUM(selling_price_paise * id), 0) FROM products),
          (SELECT COALESCE(SUM((reorder_point * id) + pack_size), 0) FROM products),
          (SELECT COALESCE(SUM(supplier_id * id), 0) FROM products),
          (SELECT COALESCE(SUM(is_active), 0) FROM products),
          (SELECT COUNT(*) FROM products),
          (SELECT COUNT(*) FROM suppliers),
          (SELECT COALESCE(SUM(base_lead_days * id), 0) FROM suppliers),
          (SELECT COALESCE(SUM(CAST(ROUND(delivery_reliability * 1000000) AS INTEGER) * id), 0) FROM suppliers)
        """
    ).fetchone()
    return (ALGORITHM_VERSION, int(seed), str(snapshot_date), tuple(row))


def source_fingerprint(conn: sqlite3.Connection, *, seed: int, snapshot_date: str) -> str:
    """SHA-256 of historical reconstruction inputs, excluding live stock."""
    key = _stamp(conn, seed, snapshot_date)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    hasher = hashlib.sha256()
    hasher.update(
        f"algorithm={ALGORITHM_VERSION}\nseed={int(seed)}\nsnapshot_date={snapshot_date}\n".encode("utf-8")
    )
    _consume(
        hasher,
        conn,
        "sales",
        """
        SELECT product_id, sale_date, units, selling_price_paise
        FROM sales
        ORDER BY product_id, sale_date, id
        """,
    )
    _consume(
        hasher,
        conn,
        "products",
        """
        SELECT id, unit_cost_paise, selling_price_paise, reorder_point, pack_size, supplier_id, is_active
        FROM products
        ORDER BY id
        """,
    )
    _consume(
        hasher,
        conn,
        "suppliers",
        """
        SELECT id, base_lead_days, printf('%.8f', delivery_reliability)
        FROM suppliers
        ORDER BY id
        """,
    )
    digest = hasher.hexdigest()
    _CACHE[key] = digest
    return digest


def anchor_fingerprint(pairs: list[tuple[int, int]]) -> str:
    hasher = hashlib.sha256()
    hasher.update(b"[anchor]\n")
    for product_id, stock in sorted((int(pid), int(stock)) for pid, stock in pairs):
        hasher.update(f"{product_id}|{stock}\n".encode("utf-8"))
    return hasher.hexdigest()


def live_anchor_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT id, stock_on_hand FROM products WHERE is_active = 1 ORDER BY id"
    ).fetchall()
    return anchor_fingerprint([(int(row["id"]), int(row["stock_on_hand"])) for row in rows])


def snapshot_anchor_fingerprint(conn: sqlite3.Connection, run_id: int, snapshot_date: str) -> tuple[str, int]:
    rows = conn.execute(
        """
        SELECT product_id, closing_stock
        FROM inventory_daily_snapshots
        WHERE run_id = ? AND snapshot_date = ?
        ORDER BY product_id
        """,
        (int(run_id), snapshot_date),
    ).fetchall()
    pairs = [(int(row["product_id"]), int(row["closing_stock"])) for row in rows]
    units = sum(stock for _, stock in pairs)
    return anchor_fingerprint(pairs), units


def backfill_missing_fingerprints(conn: sqlite3.Connection) -> int:
    """Fill fingerprints for runs created before v3.1.

    Source hashes use the historical inputs currently stored. A sale or cost
    edited after this backfill changes the hash and marks the run stale.
    Anchors are read from the terminal snapshot, not from live stock.
    """
    rows = conn.execute(
        """
        SELECT id, seed, snapshot_date, source_fingerprint, anchor_fingerprint
        FROM analytics_runs
        WHERE status IN ('complete', 'superseded')
        """
    ).fetchall()
    updated = 0
    for row in rows:
        if row["source_fingerprint"] and row["anchor_fingerprint"]:
            continue
        fingerprint = source_fingerprint(conn, seed=int(row["seed"]), snapshot_date=str(row["snapshot_date"]))
        anchor, units = snapshot_anchor_fingerprint(conn, int(row["id"]), str(row["snapshot_date"]))
        conn.execute(
            """
            UPDATE analytics_runs
            SET source_fingerprint = ?, anchor_fingerprint = ?, anchor_units = ?
            WHERE id = ?
            """,
            (fingerprint, anchor, units, int(row["id"])),
        )
        updated += 1
    if updated:
        conn.commit()
    return updated


def clear_fingerprint_cache() -> None:
    _CACHE.clear()
