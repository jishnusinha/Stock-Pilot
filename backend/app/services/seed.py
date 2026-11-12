"""Deterministic demo database seeding."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import numpy as np

from app.core.config import settings
from app.db import repositories as repo

CATEGORIES = [
    "Dairy",
    "Snacks",
    "Beverages",
    "Household",
    "Personal Care",
    "Frozen",
]
SUPPLIER_NAMES = [
    "Northwind Foods",
    "Green Valley Co-op",
    "MetroPack Logistics",
    "Sunrise Wholesale",
    "Harbor Fresh Supply",
    "Prairie Provisions",
    "Summit Distribution",
    "Riverbend Trading",
    "Atlas Commodities",
    "BlueLine Merchants",
    "Cedar Grove Imports",
    "Silver Creek Partners",
]


def _date_range(end: str, days: int) -> list[str]:
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    return [(end_dt - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d") for i in range(days)]


def seed_demo(
    conn: sqlite3.Connection,
    *,
    products: int = 200,
    days: int = 365,
    seed: int = 42,
    as_of: str | None = None,
) -> dict:
    as_of = as_of or settings.demo_date
    rng = np.random.default_rng(seed)
    for table in (
        "inventory_receipts",
        "inventory_ledger",
        "inventory_daily_snapshots",
        "analytics_runs",
    ):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists:
            conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM sales")
    conn.execute("DELETE FROM inventory_movements")
    conn.execute("DELETE FROM forecasts")
    conn.execute("DELETE FROM recommendations")
    conn.execute("DELETE FROM reorders")
    conn.execute("DELETE FROM scenario_runs")
    conn.execute("DELETE FROM agent_runs")
    conn.execute("DELETE FROM model_metrics")
    conn.execute("DELETE FROM model_versions")
    conn.execute("DELETE FROM product_risk_cache")
    conn.execute("DELETE FROM products")
    conn.execute("DELETE FROM suppliers")

    n_suppliers = int(rng.integers(8, 13))
    supplier_rows = []
    now = repo.utc_now()
    for i in range(n_suppliers):
        name = SUPPLIER_NAMES[i % len(SUPPLIER_NAMES)]
        supplier_rows.append(
            (
                name,
                int(rng.integers(3, 14)),
                float(rng.uniform(0.75, 0.98)),
                now,
            )
        )
    conn.executemany(
        "INSERT INTO suppliers(name, base_lead_days, delivery_reliability, created_at) VALUES (?,?,?,?)",
        supplier_rows,
    )
    supplier_ids = [r[0] for r in conn.execute("SELECT id FROM suppliers").fetchall()]

    dates = _date_range(as_of, days)
    product_rows = []
    low_stock_idx = set(rng.choice(products, size=max(3, products // 25), replace=False))
    high_stock_idx = set(rng.choice(products, size=max(3, products // 25), replace=False))

    for i in range(products):
        sku = f"SKU-{i+1:04d}"
        cat = CATEGORIES[i % len(CATEGORIES)]
        sid = int(supplier_ids[i % len(supplier_ids)])
        cost = int(rng.integers(500, 8000))
        price = int(cost * rng.uniform(1.15, 1.85))
        pack = int(rng.choice([6, 12, 24, 48]))
        shelf = int(rng.choice([7, 14, 30, 60, 90, 365]))
        base_demand = float(rng.uniform(0.5, 18))
        reorder = int(max(pack, round(base_demand * 7)))
        if i in low_stock_idx:
            stock = int(max(0, reorder * rng.uniform(0.05, 0.35)))
        elif i in high_stock_idx:
            stock = int(reorder * rng.uniform(3.0, 8.0))
        else:
            stock = int(reorder * rng.uniform(0.6, 2.5))
        product_rows.append(
            (
                sku,
                f"{cat} Item {i+1}",
                cat,
                sid,
                cost,
                price,
                stock,
                reorder,
                pack,
                shelf,
                1,
            )
        )

    conn.executemany(
        """
        INSERT INTO products(
          sku, name, category, supplier_id, unit_cost_paise, selling_price_paise,
          stock_on_hand, reorder_point, pack_size, shelf_life_days, is_active
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        product_rows,
    )
    pid_rows = conn.execute("SELECT id, category, selling_price_paise, reorder_point FROM products").fetchall()
    dow_season = np.sin(np.linspace(0, 8 * np.pi, days)) * 0.15 + 1.0

    sales_batch: list[tuple] = []
    chunk = 5000
    for row in pid_rows:
        pid = int(row["id"])
        base = float(rng.uniform(0.5, 16))
        try:
            ci = CATEGORIES.index(row["category"])
        except ValueError:
            ci = 0
        cat_factor = 1.0 + ci * 0.03
        price = int(row["selling_price_paise"])
        for di, d in enumerate(dates):
            units = base * cat_factor * dow_season[di] * float(rng.uniform(0.65, 1.35))
            if rng.random() < 0.08:
                units *= 0.0
            if rng.random() < 0.05:
                units *= 1.6
            promo = 1 if rng.random() < 0.06 else 0
            event = 1 if (di % 30 == 0 and rng.random() < 0.4) else 0
            if promo:
                price_day = int(price * 0.9)
            else:
                price_day = price
            sales_batch.append((pid, d, int(max(0, round(units))), price_day, promo, event))
            if len(sales_batch) >= chunk:
                conn.executemany(
                    """
                    INSERT INTO sales(product_id, sale_date, units, selling_price_paise, promo_flag, event_flag)
                    VALUES (?,?,?,?,?,?)
                    """,
                    sales_batch,
                )
                sales_batch.clear()
    if sales_batch:
        conn.executemany(
            """
            INSERT INTO sales(product_id, sale_date, units, selling_price_paise, promo_flag, event_flag)
            VALUES (?,?,?,?,?,?)
            """,
            sales_batch,
        )

    conn.commit()
    return {
        "products": products,
        "days": days,
        "suppliers": n_suppliers,
        "sales_rows": products * days,
        "as_of": as_of,
        "seed": seed,
    }
