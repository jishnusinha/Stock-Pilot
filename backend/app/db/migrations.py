"""Idempotent SQLite schema migrations."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  base_lead_days INTEGER NOT NULL,
  delivery_reliability REAL NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  unit_cost_paise INTEGER NOT NULL,
  selling_price_paise INTEGER NOT NULL,
  stock_on_hand INTEGER NOT NULL,
  reorder_point INTEGER NOT NULL,
  pack_size INTEGER NOT NULL,
  shelf_life_days INTEGER,
  is_active INTEGER NOT NULL DEFAULT 1,
  CHECK (stock_on_hand >= 0),
  CHECK (unit_cost_paise >= 0),
  CHECK (selling_price_paise >= 0),
  CHECK (pack_size >= 1)
);

CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id),
  sale_date TEXT NOT NULL,
  units INTEGER NOT NULL,
  selling_price_paise INTEGER NOT NULL,
  promo_flag INTEGER NOT NULL DEFAULT 0,
  event_flag INTEGER NOT NULL DEFAULT 0,
  UNIQUE(product_id, sale_date),
  CHECK (units >= 0),
  CHECK (selling_price_paise >= 0)
);

CREATE TABLE IF NOT EXISTS inventory_movements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id),
  delta_units INTEGER NOT NULL,
  reason TEXT NOT NULL,
  reference TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS forecasts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id),
  as_of_date TEXT NOT NULL,
  target_date TEXT NOT NULL,
  p10_units REAL NOT NULL,
  p50_units REAL NOT NULL,
  p90_units REAL NOT NULL,
  model_version TEXT NOT NULL,
  provenance TEXT NOT NULL,
  UNIQUE(product_id, as_of_date, target_date, model_version)
);

CREATE TABLE IF NOT EXISTS recommendations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id),
  created_at TEXT NOT NULL,
  suggested_qty INTEGER NOT NULL,
  expected_stockout_risk REAL,
  expected_excess_risk REAL,
  estimated_cost_paise INTEGER,
  expected_arrival_date TEXT,
  explanation_json TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  trace_id TEXT
);

CREATE TABLE IF NOT EXISTS reorders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id),
  recommendation_id INTEGER REFERENCES recommendations(id),
  qty INTEGER NOT NULL,
  unit_cost_paise INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  reviewed_at TEXT,
  notes TEXT,
  CHECK (qty >= 0),
  CHECK (unit_cost_paise >= 0)
);

CREATE TABLE IF NOT EXISTS scenario_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id),
  created_at TEXT NOT NULL,
  name TEXT,
  input_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  provenance TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trace_id TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  started_at TEXT NOT NULL,
  duration_ms REAL NOT NULL,
  status TEXT NOT NULL,
  model_version TEXT,
  provenance TEXT,
  input_summary_json TEXT,
  output_summary_json TEXT,
  error_text TEXT
);

CREATE TABLE IF NOT EXISTS model_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_name TEXT NOT NULL,
  version TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  metric_value REAL,
  evaluation_split TEXT NOT NULL,
  dataset_source TEXT NOT NULL,
  computed_at TEXT NOT NULL,
  metric_display TEXT
);

CREATE TABLE IF NOT EXISTS model_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_name TEXT NOT NULL,
  version TEXT NOT NULL,
  artifact_file TEXT NOT NULL,
  training_source TEXT NOT NULL,
  train_start TEXT,
  train_end TEXT,
  test_start TEXT,
  test_end TEXT,
  trained_at TEXT NOT NULL,
  metadata_json TEXT,
  UNIQUE(agent_name, version)
);

CREATE TABLE IF NOT EXISTS product_risk_cache (
  product_id INTEGER PRIMARY KEY REFERENCES products(id),
  risk_level TEXT NOT NULL,
  days_of_supply REAL,
  forecast_28d REAL,
  sell_through REAL,
  stockout_risk REAL,
  updated_at TEXT NOT NULL,
  provenance TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_product_date ON sales(product_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_product ON forecasts(product_id, as_of_date);
CREATE INDEX IF NOT EXISTS idx_recommendations_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_reorders_status ON reorders(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_trace ON agent_runs(trace_id);
CREATE INDEX IF NOT EXISTS idx_movements_product ON inventory_movements(product_id, created_at);
"""


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_V1)
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?", ("v1",)
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            ("v1", datetime.now(timezone.utc).isoformat()),
        )
    conn.commit()


def migrate_path(db_path: Path) -> None:
    from app.db.connection import connect

    conn = connect(db_path)
    try:
        migrate(conn)
    finally:
        conn.close()
