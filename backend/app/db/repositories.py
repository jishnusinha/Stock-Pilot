"""Data access — parameterized SQL only."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- products / suppliers ----

def list_suppliers(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, base_lead_days, delivery_reliability FROM suppliers ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def get_product(conn: sqlite3.Connection, product_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT p.*, s.name AS supplier_name, s.base_lead_days, s.delivery_reliability
        FROM products p JOIN suppliers s ON s.id = p.supplier_id
        WHERE p.id = ?
        """,
        (product_id,),
    ).fetchone()
    return dict(row) if row else None


def get_product_by_sku(conn: sqlite3.Connection, sku: str) -> dict | None:
    row = conn.execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()
    return dict(row) if row else None


def count_products(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM products WHERE is_active=1").fetchone()[0])


def list_products(
    conn: sqlite3.Connection,
    *,
    search: str | None = None,
    category: str | None = None,
    supplier_id: int | None = None,
    risk: str | None = None,
    sort: str = "sku",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    where = ["p.is_active = 1"]
    params: list[Any] = []
    if search:
        where.append("(p.name LIKE ? OR p.sku LIKE ?)")
        q = f"%{search}%"
        params.extend([q, q])
    if category:
        where.append("p.category = ?")
        params.append(category)
    if supplier_id is not None:
        where.append("p.supplier_id = ?")
        params.append(supplier_id)
    if risk:
        levels = [x.strip().lower() for x in risk.split(",") if x.strip()]
        if levels:
            placeholders = ",".join("?" for _ in levels)
            where.append(f"LOWER(COALESCE(r.risk_level,'unknown')) IN ({placeholders})")
            params.extend(levels)

    sort_map = {
        "sku": "p.sku ASC",
        "name": "p.name ASC",
        "stock": "p.stock_on_hand DESC",
        "risk": "CASE r.risk_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, p.sku",
        "dos": "COALESCE(r.days_of_supply, 9999) ASC",
    }
    order = sort_map.get(sort, "p.sku ASC")
    where_sql = " AND ".join(where)

    total = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM products p
        LEFT JOIN product_risk_cache r ON r.product_id = p.id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE {where_sql}
        """,
        params,
    ).fetchone()[0]

    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""
        SELECT p.*, s.name AS supplier_name, s.base_lead_days,
               r.risk_level, r.days_of_supply, r.forecast_28d, r.sell_through,
               r.stockout_risk, r.updated_at AS risk_updated_at, r.provenance AS risk_provenance
        FROM products p
        LEFT JOIN product_risk_cache r ON r.product_id = p.id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE {where_sql}
        ORDER BY {order}
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()
    return [dict(r) for r in rows], int(total)


def create_product(conn: sqlite3.Connection, data: dict) -> dict:
    sku = str(data["sku"]).strip()
    if not sku:
        raise ValueError("SKU is required")
    if get_product_by_sku(conn, sku):
        raise ValueError(f"SKU already exists: {sku}")
    stock = int(data.get("stock_on_hand", 0))
    if stock < 0:
        raise ValueError("Stock cannot be negative")
    cost = int(data["unit_cost_paise"])
    price = int(data["selling_price_paise"])
    if cost < 0 or price <= 0:
        raise ValueError("Invalid cost or price")
    pack = max(1, int(data.get("pack_size", 12)))
    cur = conn.execute(
        """
        INSERT INTO products(
          sku, name, category, supplier_id, unit_cost_paise, selling_price_paise,
          stock_on_hand, reorder_point, pack_size, shelf_life_days, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            sku,
            str(data["name"]).strip(),
            str(data.get("category") or "General").strip(),
            int(data["supplier_id"]),
            cost,
            price,
            stock,
            int(data.get("reorder_point", pack)),
            pack,
            data.get("shelf_life_days"),
        ),
    )
    pid = int(cur.lastrowid)
    if stock:
        conn.execute(
            """
            INSERT INTO inventory_movements(product_id, delta_units, reason, reference, created_at)
            VALUES (?, ?, 'initial_stock', ?, ?)
            """,
            (pid, stock, f"create:{sku}", utc_now()),
        )
    repo_upsert_default_risk(conn, pid, stock)
    out = get_product(conn, pid)
    assert out is not None
    return out


def update_product(conn: sqlite3.Connection, product_id: int, data: dict) -> dict:
    existing = get_product(conn, product_id)
    if not existing:
        raise ValueError("Product not found")
    name = str(data.get("name", existing["name"])).strip()
    category = str(data.get("category", existing["category"])).strip()
    supplier_id = int(data.get("supplier_id", existing["supplier_id"]))
    cost = int(data.get("unit_cost_paise", existing["unit_cost_paise"]))
    price = int(data.get("selling_price_paise", existing["selling_price_paise"]))
    reorder_point = int(data.get("reorder_point", existing["reorder_point"]))
    pack = max(1, int(data.get("pack_size", existing["pack_size"])))
    shelf = data.get("shelf_life_days", existing.get("shelf_life_days"))
    if cost < 0 or price <= 0:
        raise ValueError("Invalid cost or price")
    conn.execute(
        """
        UPDATE products SET
          name=?, category=?, supplier_id=?, unit_cost_paise=?, selling_price_paise=?,
          reorder_point=?, pack_size=?, shelf_life_days=?
        WHERE id=?
        """,
        (name, category, supplier_id, cost, price, reorder_point, pack, shelf, product_id),
    )
    out = get_product(conn, product_id)
    assert out is not None
    return out


def soft_delete_product(conn: sqlite3.Connection, product_id: int) -> None:
    existing = get_product(conn, product_id)
    if not existing:
        raise ValueError("Product not found")
    conn.execute("UPDATE products SET is_active=0 WHERE id=?", (product_id,))
    conn.execute("DELETE FROM product_risk_cache WHERE product_id=?", (product_id,))


def repo_upsert_default_risk(conn: sqlite3.Connection, product_id: int, stock: int) -> None:
    upsert_risk_cache(
        conn,
        product_id,
        {
            "risk_level": "medium" if stock < 20 else "low",
            "days_of_supply": None,
            "forecast_28d": None,
            "sell_through": None,
            "stockout_risk": None,
            "provenance": "SYNTHETIC_DEMO",
        },
    )


def adjust_stock(
    conn: sqlite3.Connection,
    product_id: int,
    delta: int,
    reason: str,
    reference: str | None = None,
) -> dict:
    row = conn.execute(
        "SELECT stock_on_hand FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if not row:
        raise ValueError("Product not found")
    new_stock = int(row["stock_on_hand"]) + int(delta)
    if new_stock < 0:
        raise ValueError("Stock cannot become negative")
    conn.execute(
        "UPDATE products SET stock_on_hand = ? WHERE id = ?",
        (new_stock, product_id),
    )
    conn.execute(
        """
        INSERT INTO inventory_movements(product_id, delta_units, reason, reference, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (product_id, delta, reason, reference, utc_now()),
    )
    # Mark cached risk/recommendations stale until re-run decision
    conn.execute(
        """
        UPDATE product_risk_cache
        SET risk_level = 'medium',
            updated_at = ?,
            provenance = COALESCE(provenance, '') || '|STALE_AFTER_STOCK_ADJUST'
        WHERE product_id = ?
        """,
        (utc_now(), product_id),
    )
    conn.execute(
        """
        UPDATE recommendations
        SET status = 'stale'
        WHERE product_id = ? AND status IN ('open', 'proposed', 'pending', 'active')
        """,
        (product_id,),
    )
    return get_product(conn, product_id)  # type: ignore[return-value]


def sales_range(
    conn: sqlite3.Connection, product_id: int, start: str, end: str
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT sale_date, units, selling_price_paise, promo_flag, event_flag
        FROM sales WHERE product_id = ? AND sale_date >= ? AND sale_date <= ?
        ORDER BY sale_date
        """,
        (product_id, start, end),
    ).fetchall()
    return [dict(r) for r in rows]


def recent_movements(conn: sqlite3.Connection, product_id: int, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, delta_units, reason, reference, created_at
        FROM inventory_movements WHERE product_id = ?
        ORDER BY created_at DESC LIMIT ?
        """,
        (product_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_risk_cache(conn: sqlite3.Connection, product_id: int, payload: dict) -> None:
    conn.execute(
        """
        INSERT INTO product_risk_cache(
          product_id, risk_level, days_of_supply, forecast_28d, sell_through,
          stockout_risk, updated_at, provenance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
          risk_level=excluded.risk_level,
          days_of_supply=excluded.days_of_supply,
          forecast_28d=excluded.forecast_28d,
          sell_through=excluded.sell_through,
          stockout_risk=excluded.stockout_risk,
          updated_at=excluded.updated_at,
          provenance=excluded.provenance
        """,
        (
            product_id,
            payload["risk_level"],
            payload.get("days_of_supply"),
            payload.get("forecast_28d"),
            payload.get("sell_through"),
            payload.get("stockout_risk"),
            payload.get("updated_at", utc_now()),
            payload.get("provenance", "SYNTHETIC_DEMO"),
        ),
    )


# ---- forecasts / recommendations / reorders / scenarios ----

def replace_forecasts(
    conn: sqlite3.Connection,
    product_id: int,
    as_of: str,
    model_version: str,
    series: list[dict],
    provenance: str,
) -> None:
    conn.execute(
        "DELETE FROM forecasts WHERE product_id=? AND as_of_date=? AND model_version=?",
        (product_id, as_of, model_version),
    )
    conn.executemany(
        """
        INSERT INTO forecasts(
          product_id, as_of_date, target_date, p10_units, p50_units, p90_units,
          model_version, provenance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                product_id,
                as_of,
                s["target_date"],
                s["p10_units"],
                s["p50_units"],
                s["p90_units"],
                model_version,
                provenance,
            )
            for s in series
        ],
    )


def get_forecasts(conn: sqlite3.Connection, product_id: int, as_of: str | None = None) -> list[dict]:
    if as_of:
        rows = conn.execute(
            """
            SELECT * FROM forecasts WHERE product_id=? AND as_of_date=?
            ORDER BY target_date
            """,
            (product_id, as_of),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM forecasts WHERE product_id=?
              AND as_of_date = (SELECT MAX(as_of_date) FROM forecasts WHERE product_id=?)
            ORDER BY target_date
            """,
            (product_id, product_id),
        ).fetchall()
    return [dict(r) for r in rows]


def insert_recommendation(conn: sqlite3.Connection, data: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO recommendations(
          product_id, created_at, suggested_qty, expected_stockout_risk,
          expected_excess_risk, estimated_cost_paise, expected_arrival_date,
          explanation_json, status, trace_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["product_id"],
            data.get("created_at", utc_now()),
            data["suggested_qty"],
            data.get("expected_stockout_risk"),
            data.get("expected_excess_risk"),
            data.get("estimated_cost_paise"),
            data.get("expected_arrival_date"),
            json.dumps(data.get("explanation_json") or {}),
            data.get("status", "open"),
            data.get("trace_id"),
        ),
    )
    return int(cur.lastrowid)


def get_open_recommendations(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """
        SELECT r.*, p.sku, p.name AS product_name,
               c.risk_level, c.days_of_supply
        FROM recommendations r
        JOIN products p ON p.id = r.product_id
        LEFT JOIN product_risk_cache c ON c.product_id = r.product_id
        WHERE r.status = 'open'
        ORDER BY
          CASE c.risk_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
          CASE WHEN r.suggested_qty > 0 THEN 0 ELSE 1 END,
          COALESCE(c.days_of_supply, 9999) ASC,
          COALESCE(r.expected_stockout_risk, 0) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_reorder(
    conn: sqlite3.Connection,
    product_id: int,
    qty: int,
    unit_cost_paise: int,
    recommendation_id: int | None = None,
    notes: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO reorders(
          product_id, recommendation_id, qty, unit_cost_paise, status, created_at, notes
        ) VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """,
        (product_id, recommendation_id, qty, unit_cost_paise, utc_now(), notes),
    )
    if recommendation_id:
        conn.execute(
            "UPDATE recommendations SET status='proposed' WHERE id=?",
            (recommendation_id,),
        )
    return int(cur.lastrowid)


def list_reorders(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    if status:
        rows = conn.execute(
            """
            SELECT o.*, p.sku, p.name AS product_name
            FROM reorders o JOIN products p ON p.id = o.product_id
            WHERE o.status = ?
            ORDER BY o.created_at DESC
            """,
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT o.*, p.sku, p.name AS product_name
            FROM reorders o JOIN products p ON p.id = o.product_id
            ORDER BY o.created_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_reorder(conn: sqlite3.Connection, reorder_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM reorders WHERE id=?", (reorder_id,)).fetchone()
    return dict(row) if row else None


def set_reorder_status(conn: sqlite3.Connection, reorder_id: int, status: str) -> dict:
    row = get_reorder(conn, reorder_id)
    if not row:
        raise ValueError("Reorder not found")
    if status == "approved" and row["status"] != "pending":
        raise ValueError("Only pending reorders can be approved")
    if status == "rejected" and row["status"] != "pending":
        raise ValueError("Only pending reorders can be rejected")
    if status == "received" and row["status"] != "approved":
        raise ValueError("Only approved reorders can be received")
    conn.execute(
        "UPDATE reorders SET status=?, reviewed_at=? WHERE id=?",
        (status, utc_now(), reorder_id),
    )
    if status == "received":
        # Idempotency: check if movement already exists for this reorder
        existing = conn.execute(
            """
            SELECT 1 FROM inventory_movements
            WHERE reference = ? AND reason = 'receive_reorder'
            """,
            (f"reorder:{reorder_id}",),
        ).fetchone()
        if not existing:
            adjust_stock(
                conn,
                int(row["product_id"]),
                int(row["qty"]),
                reason="receive_reorder",
                reference=f"reorder:{reorder_id}",
            )
    updated = get_reorder(conn, reorder_id)
    assert updated is not None
    return updated


def save_scenario(
    conn: sqlite3.Connection,
    product_id: int,
    input_data: dict,
    result: dict,
    provenance: str,
    name: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO scenario_runs(product_id, created_at, name, input_json, result_json, provenance)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            product_id,
            utc_now(),
            name,
            json.dumps(input_data),
            json.dumps(result),
            provenance,
        ),
    )
    return int(cur.lastrowid)


def list_scenarios(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.id, s.product_id, s.created_at, s.name, s.provenance, p.sku, p.name AS product_name
        FROM scenario_runs s JOIN products p ON p.id = s.product_id
        ORDER BY s.created_at DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_agent_run(conn: sqlite3.Connection, data: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO agent_runs(
          trace_id, agent_name, started_at, duration_ms, status, model_version,
          provenance, input_summary_json, output_summary_json, error_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["trace_id"],
            data["agent_name"],
            data["started_at"],
            data["duration_ms"],
            data["status"],
            data.get("model_version"),
            data.get("provenance"),
            json.dumps(data.get("input_summary") or {}),
            json.dumps(data.get("output_summary") or {}),
            data.get("error_text"),
        ),
    )
    return int(cur.lastrowid)


def list_agent_runs(
    conn: sqlite3.Connection, *, page: int = 1, page_size: int = 20, agent_name: str | None = None
) -> tuple[list[dict], int]:
    where = ["1=1"]
    params: list[Any] = []
    if agent_name:
        where.append("agent_name = ?")
        params.append(agent_name)
    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(DISTINCT trace_id) FROM agent_runs WHERE {where_sql}", params
    ).fetchone()[0]
    offset = (max(1, page) - 1) * page_size
    # latest row per trace
    rows = conn.execute(
        f"""
        SELECT trace_id,
               MIN(started_at) AS started_at,
               SUM(duration_ms) AS total_duration_ms,
               GROUP_CONCAT(DISTINCT agent_name) AS agents,
               MAX(status) AS status
        FROM agent_runs
        WHERE {where_sql}
        GROUP BY trace_id
        ORDER BY started_at DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()
    return [dict(r) for r in rows], int(total)


def get_trace(conn: sqlite3.Connection, trace_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM agent_runs WHERE trace_id = ? ORDER BY started_at, id
        """,
        (trace_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_model_version(conn: sqlite3.Connection, data: dict) -> None:
    conn.execute(
        """
        INSERT INTO model_versions(
          agent_name, version, artifact_file, training_source,
          train_start, train_end, test_start, test_end, trained_at, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_name, version) DO UPDATE SET
          artifact_file=excluded.artifact_file,
          training_source=excluded.training_source,
          train_start=excluded.train_start,
          train_end=excluded.train_end,
          test_start=excluded.test_start,
          test_end=excluded.test_end,
          trained_at=excluded.trained_at,
          metadata_json=excluded.metadata_json
        """,
        (
            data["agent_name"],
            data["version"],
            data["artifact_file"],
            data["training_source"],
            data.get("train_start"),
            data.get("train_end"),
            data.get("test_start"),
            data.get("test_end"),
            data.get("trained_at", utc_now()),
            json.dumps(data.get("metadata") or {}),
        ),
    )


def insert_metric(conn: sqlite3.Connection, data: dict) -> None:
    conn.execute(
        """
        INSERT INTO model_metrics(
          agent_name, version, metric_name, metric_value, evaluation_split,
          dataset_source, computed_at, metric_display
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["agent_name"],
            data["version"],
            data["metric_name"],
            data.get("metric_value"),
            data["evaluation_split"],
            data["dataset_source"],
            data.get("computed_at", utc_now()),
            data.get("metric_display"),
        ),
    )


def clear_metrics_for_eval(conn: sqlite3.Connection, evaluation_split: str) -> None:
    conn.execute(
        "DELETE FROM model_metrics WHERE evaluation_split = ?", (evaluation_split,)
    )


def list_metrics(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM model_metrics ORDER BY computed_at DESC, agent_name, metric_name
        """
    ).fetchall()
    return [dict(r) for r in rows]


def list_model_versions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM model_versions ORDER BY agent_name, trained_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def dashboard_aggregates(conn: sqlite3.Connection) -> dict:
    n_products = count_products(conn)
    high_risk = conn.execute(
        "SELECT COUNT(*) FROM product_risk_cache WHERE risk_level='high'"
    ).fetchone()[0]
    open_rec = conn.execute(
        "SELECT COUNT(*) FROM recommendations WHERE status IN ('open','proposed')"
    ).fetchone()[0]
    pending_reorders = conn.execute(
        "SELECT COUNT(*) FROM reorders WHERE status='pending'"
    ).fetchone()[0]
    return {
        "n_products": n_products,
        "high_risk": int(high_risk),
        "open_recommendations": int(open_rec),
        "pending_reorders": int(pending_reorders),
    }
