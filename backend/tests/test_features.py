import pandas as pd

from app.ml.features import build_product_features, FEATURE_COLUMNS


def test_rolling_uses_shift_no_leakage():
    df = pd.DataFrame(
        {
            "sale_date": pd.date_range("2026-01-01", periods=40, freq="D"),
            "units": list(range(40)),
            "selling_price_paise": [100] * 40,
            "promo_flag": 0,
            "event_flag": 0,
        }
    )
    out = build_product_features(df)
    # lag_1 at index for day 29 should be 28
    row = out.iloc[29]
    assert row["lag_1"] == 28
    assert "roll_mean_7" in FEATURE_COLUMNS
    # first row with all lags present is at least day 28 (0-indexed 28)
    assert pd.isna(out.iloc[0]["lag_28"])
