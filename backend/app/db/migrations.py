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

SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS analytics_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_source TEXT NOT NULL,
  seed INTEGER NOT NULL,
  snapshot_date TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  version TEXT NOT NULL,
  status TEXT NOT NULL,
  product_count INTEGER,
  day_count INTEGER,
  notes TEXT,
  UNIQUE(dataset_source, seed, snapshot_date, version)
);

CREATE TABLE IF NOT EXISTS inventory_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES analytics_runs(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  event_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  quantity_change INTEGER NOT NULL,
  unit_cost_paise INTEGER NOT NULL,
  reference TEXT,
  provenance TEXT NOT NULL,
  CHECK (unit_cost_paise >= 0),
  CHECK (event_type IN ('opening','receipt','sale','return','adjustment','writeoff'))
);

CREATE TABLE IF NOT EXISTS inventory_daily_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES analytics_runs(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  snapshot_date TEXT NOT NULL,
  opening_stock INTEGER NOT NULL,
  received_units INTEGER NOT NULL,
  sold_units INTEGER NOT NULL,
  returned_units INTEGER NOT NULL,
  adjustment_units INTEGER NOT NULL,
  writeoff_units INTEGER NOT NULL,
  unmet_demand_units INTEGER NOT NULL,
  demand_units INTEGER NOT NULL,
  closing_stock INTEGER NOT NULL,
  unit_cost_paise INTEGER NOT NULL,
  closing_value_paise INTEGER NOT NULL,
  cogs_paise INTEGER NOT NULL,
  revenue_paise INTEGER NOT NULL,
  provenance TEXT NOT NULL,
  UNIQUE(run_id, product_id, snapshot_date),
  CHECK (opening_stock >= 0),
  CHECK (closing_stock >= 0),
  CHECK (received_units >= 0),
  CHECK (sold_units >= 0),
  CHECK (returned_units >= 0),
  CHECK (writeoff_units >= 0),
  CHECK (unmet_demand_units >= 0),
  CHECK (demand_units >= 0),
  CHECK (unit_cost_paise >= 0),
  CHECK (closing_value_paise >= 0),
  CHECK (cogs_paise >= 0),
  CHECK (revenue_paise >= 0)
);

CREATE TABLE IF NOT EXISTS inventory_receipts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES analytics_runs(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
  ordered_date TEXT NOT NULL,
  promised_date TEXT NOT NULL,
  received_date TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  delay_days INTEGER NOT NULL,
  on_time INTEGER NOT NULL,
  kind TEXT NOT NULL,
  provenance TEXT NOT NULL,
  CHECK (quantity >= 0),
  CHECK (on_time IN (0, 1)),
  CHECK (kind IN ('replenishment','reconciliation'))
);

CREATE INDEX IF NOT EXISTS idx_snap_run_date ON inventory_daily_snapshots(run_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snap_run_product ON inventory_daily_snapshots(run_id, product_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_ledger_run_product ON inventory_ledger(run_id, product_id, event_at);
CREATE INDEX IF NOT EXISTS idx_receipts_run_supplier ON inventory_receipts(run_id, supplier_id, received_date);
CREATE INDEX IF NOT EXISTS idx_analytics_runs_status ON analytics_runs(status, generated_at);
"""


def _mark(conn: sqlite3.Connection, version: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
    ).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_V1)
    conn.executescript(SCHEMA_V3)
    _mark(conn, "v1")
    _mark(conn, "v3")
    conn.commit()


def migrate_path(db_path: Path) -> None:
    from app.db.connection import connect

    conn = connect(db_path)
    try:
        migrate(conn)
    finally:
        conn.close()
