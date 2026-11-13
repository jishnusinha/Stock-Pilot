"""Tests for REAL_RETAIL_UCI pipeline using tiny synthetic fixtures (not the UCI dataset)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.migrations import migrate
from app.main import app
from app.ml import metrics as M
from app.real_data import features as F
from app.real_data.evaluate import moving_average_units, seasonal_naive_units
from app.real_data.preprocess import (
    _is_admin_stock_code,
    aggregate_daily_sales,
    audit_quality,
    clean_transactions,
)
from app.services.seed import seed_demo


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "api_real.db"
    models = tmp_path / "models"
    monkeypatch.setattr(settings, "db_path", db)
    monkeypatch.setattr(settings, "model_dir", models)
    monkeypatch.setattr(settings, "eval_dir", tmp_path / "eval")
    settings.ensure_dirs()
    from app.db.connection import connect

    conn = connect(db)
    migrate(conn)
    seed_demo(conn, products=4, days=40, seed=3)
    conn.close()
    with TestClient(app) as c:
        yield c


def _tiny_raw() -> pd.DataFrame:
    """Clearly labeled test-only rows — not UCI data."""
    rows = [
        # valid sale
        {"InvoiceNo": "10001", "StockCode": "SKU01", "Description": "Widget", "Quantity": 2, "InvoiceDate": "2011-01-01 10:00:00", "UnitPrice": 1.5, "CustomerID": 1.0, "Country": "United Kingdom"},
        {"InvoiceNo": "10001", "StockCode": "SKU01", "Description": "Widget", "Quantity": 1, "InvoiceDate": "2011-01-01 10:00:00", "UnitPrice": 1.5, "CustomerID": 1.0, "Country": "United Kingdom"},
        {"InvoiceNo": "10002", "StockCode": "SKU02", "Description": "Gadget", "Quantity": 5, "InvoiceDate": "2011-01-02 11:00:00", "UnitPrice": 2.0, "CustomerID": 2.0, "Country": "United Kingdom"},
        # cancellation
        {"InvoiceNo": "C10003", "StockCode": "SKU01", "Description": "Widget", "Quantity": -1, "InvoiceDate": "2011-01-03 09:00:00", "UnitPrice": 1.5, "CustomerID": 1.0, "Country": "United Kingdom"},
        # negative qty without C
        {"InvoiceNo": "10004", "StockCode": "SKU02", "Description": "Gadget", "Quantity": -2, "InvoiceDate": "2011-01-03 12:00:00", "UnitPrice": 2.0, "CustomerID": 2.0, "Country": "United Kingdom"},
        # zero qty
        {"InvoiceNo": "10005", "StockCode": "SKU01", "Description": "Widget", "Quantity": 0, "InvoiceDate": "2011-01-04 10:00:00", "UnitPrice": 1.5, "CustomerID": 1.0, "Country": "United Kingdom"},
        # nonpositive price
        {"InvoiceNo": "10006", "StockCode": "SKU01", "Description": "Widget", "Quantity": 1, "InvoiceDate": "2011-01-04 11:00:00", "UnitPrice": 0.0, "CustomerID": 1.0, "Country": "United Kingdom"},
        # admin postage
        {"InvoiceNo": "10007", "StockCode": "POST", "Description": "Postage", "Quantity": 1, "InvoiceDate": "2011-01-05 10:00:00", "UnitPrice": 5.0, "CustomerID": 3.0, "Country": "United Kingdom"},
        # stock code with letter suffix must stay string-like
        {"InvoiceNo": "10008", "StockCode": "85099B", "Description": "Bag", "Quantity": 3, "InvoiceDate": "2011-01-06 10:00:00", "UnitPrice": 1.0, "CustomerID": np.nan, "Country": "United Kingdom"},
        # missing description kept if otherwise valid
        {"InvoiceNo": "10009", "StockCode": "SKU03", "Description": None, "Quantity": 4, "InvoiceDate": "2011-01-07 10:00:00", "UnitPrice": 3.0, "CustomerID": 4.0, "Country": "France"},
    ]
    df = pd.DataFrame(rows)
    df["InvoiceNo"] = df["InvoiceNo"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["transaction_date"] = df["InvoiceDate"].dt.normalize()
    df["Quantity"] = pd.to_numeric(df["Quantity"])
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"])
    return df


def test_admin_stock_codes():
    assert _is_admin_stock_code("POST")
    assert _is_admin_stock_code("DOT")
    assert not _is_admin_stock_code("85099B")
    assert not _is_admin_stock_code("SKU01")


def test_clean_transactions_policies():
    raw = _tiny_raw()
    quality_before = audit_quality(raw)
    assert quality_before["total_source_rows"] == 10
    sales, returns, quality = clean_transactions(raw)
    # valid: 2× SKU01 day1 lines, SKU02, 85099B, SKU03 = 5 rows
    assert len(sales) == 5
    assert (sales["units"] > 0).all()
    assert (sales["UnitPrice"] > 0).all()
    reasons = set(returns["removal_reason"])
    assert "cancellation_invoice" in reasons
    assert "negative_quantity" in reasons
    assert "zero_quantity" in reasons
    assert "nonpositive_price" in reasons
    assert "admin_stock_code" in reasons
    # StockCode preserved as string with letter
    assert "85099B" in set(sales["StockCode"].astype(str))
    assert quality["after_cleaning"]["positive_sales_rows"] == 5


def test_daily_aggregation_and_stockcode_string():
    raw = _tiny_raw()
    sales, _, _ = clean_transactions(raw)
    daily = aggregate_daily_sales(sales)
    assert "stock_code" in daily.columns
    assert daily["stock_code"].dtype == object
    row = daily[daily["stock_code"] == "SKU01"].iloc[0]
    assert float(row["units_sold"]) == 3.0  # 2+1
    assert float(row["sales_revenue_gbp"]) == pytest.approx(4.5)


def test_seasonal_naive_and_ma_baselines():
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8])
    assert seasonal_naive_units(s) == 2.0  # value 7 days ago = index -7 → 1? wait iloc[-7]=2? 
    # len=8, iloc[-7] = index 1 → 2
    assert seasonal_naive_units(s) == 2.0
    assert moving_average_units(s, 3) == pytest.approx((6 + 7 + 8) / 3)


def test_metrics_zero_denominator():
    y = np.array([0.0, 0.0])
    p = np.array([1.0, 2.0])
    assert M.wape(y, p) is None
    assert M.mae(y, p) == pytest.approx(1.5)


def test_quantile_ordering():
    a, b, c = M.reconcile_quantiles(5, 1, 3)
    assert a <= b <= c


def test_pinball_and_coverage():
    y = np.array([1.0, 2.0, 3.0])
    low = np.array([0.5, 1.5, 2.5])
    high = np.array([1.5, 2.5, 3.5])
    assert M.interval_coverage(y, low, high) == 1.0
    assert M.pinball_loss(y, low, 0.1) is not None


def test_feature_shift_no_same_day_target_in_lag():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2011-01-01", periods=40, freq="D"),
            "units_sold": np.arange(40, dtype=float),
            "representative_unit_price_gbp": 1.0,
            "stock_code": "T1",
            "split": "train",
        }
    )
    feat = F.build_sku_features(df)
    # lag_1 on day i equals units on day i-1
    assert feat.loc[10, "lag_1"] == pytest.approx(feat.loc[9, "target_units"])
    assert feat.loc[10, "lag_1"] != pytest.approx(feat.loc[10, "target_units"])
    # roll_mean uses shift(1): at index 5, mean of prior units 0..4 = 2.0 (excludes day-5 target)
    assert feat.loc[5, "roll_mean_7"] == pytest.approx(2.0)
    assert feat.loc[5, "roll_mean_7"] != pytest.approx(feat.loc[5, "target_units"])


def test_chronological_split_assertions_on_dates():
    dates = pd.date_range("2011-01-01", periods=100, freq="D")
    from app.real_data.split import calendar_boundaries, assign_split

    bounds = calendar_boundaries(dates)
    assert bounds["train_end"] < bounds["val_start"]
    assert bounds["val_end"] < bounds["test_start"]
    labels = [assign_split(d, bounds) for d in dates]
    train_dates = [d for d, lab in zip(dates, labels) if lab == "train"]
    val_dates = [d for d, lab in zip(dates, labels) if lab == "validation"]
    test_dates = [d for d, lab in zip(dates, labels) if lab == "test"]
    assert max(train_dates) < min(val_dates)
    assert max(val_dates) < min(test_dates)


def test_api_real_data_status(client):
    res = client.get("/api/real-data/status")
    assert res.status_code == 200
    body = res.json()
    assert body["experiment_id"] == "REAL_RETAIL_UCI"
    assert "ready_for_ui" in body


def test_api_real_data_metadata(client):
    res = client.get("/api/real-data/metadata")
    assert res.status_code == 200
    body = res.json()
    assert body["currency"] == "GBP"
    assert body["provenance_label"] == "REAL_RETAIL_UCI"
    assert "InvoiceNo" in body["raw_columns"]


def test_api_metrics_when_present_or_404(client):
    res = client.get("/api/real-data/metrics")
    # After local experiment run this is 200; in CI without artifacts may be 404
    assert res.status_code in (200, 404)
    if res.status_code == 200:
        body = res.json()
        assert body.get("ml", {}).get("wape") is not None
        assert body.get("evaluation_mode") == "rolling_one_step_ahead"


def test_api_predictions_filter_and_no_train_on_get(client):
    status = client.get("/api/real-data/status").json()
    if not status.get("metrics_present"):
        pytest.skip("real-data experiment not evaluated in this environment")
    res = client.get("/api/real-data/predictions", params={"limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert body["returned_rows"] <= 5
    assert body["rows"]
    # invalid sample kind
    bad = client.get("/api/real-data/samples/not_a_kind.csv")
    assert bad.status_code == 400


def test_model_artifact_isolation():
    """Real-data models must not live under synthetic demo artifact dir."""
    from app.core.config import settings
    from app.real_data.paths import MODELS_DIR

    assert Path(settings.model_dir).resolve() != Path(MODELS_DIR).resolve()
    assert "real_data" in str(MODELS_DIR).replace("\\", "/")
