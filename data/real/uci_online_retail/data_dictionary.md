# UCI Online Retail — data dictionary

Experiment id: `REAL_RETAIL_UCI`  
Currency: GBP  
Source: https://archive.ics.uci.edu/dataset/352/online+retail

## Raw workbook columns

| Column | Type | Meaning |
|--------|------|---------|
| InvoiceNo | string | Invoice identifier. Values starting with `C` indicate cancellations. |
| StockCode | string | Product code. **Must remain string** (leading zeros / letter suffixes). |
| Description | string | Item text; may be missing. |
| Quantity | number | Units on the line. Negatives often returns/cancellations. |
| InvoiceDate | datetime | Source timestamp **without guaranteed timezone**. |
| UnitPrice | number | Unit price in **GBP**. |
| CustomerID | number/null | Customer id; often missing for guest checkouts. |
| Country | string | Shipping country. |

Derived while reading: `transaction_date` = calendar date of `InvoiceDate` (no timezone conversion).

## Processed — `transactions_clean.csv`

Positive fulfilled sales only (after cleaning). Includes `units`, `line_revenue_gbp`, `removal_reason=kept_positive_sale`.

## Processed — `returns_summary.csv`

Rows excluded from demand modeling with `removal_reason` in:

- `cancellation_invoice`
- `negative_quantity`
- `zero_quantity`
- `nonpositive_price`
- `missing_invoice_date`
- `admin_stock_code`
- `missing_quantity`

Returns are **not** subtracted from unrelated sales dates (matching is unreliable).

## Processed — `daily_sales.csv`

One row per observed `StockCode × date` with recorded positive sales (before densification).

| Column | Meaning |
|--------|---------|
| date | YYYY-MM-DD |
| product_id | Stable local integer mapped from StockCode |
| stock_code | Original StockCode string |
| description | Last seen description |
| units_sold | Sum of positive quantities that day |
| sales_revenue_gbp | Sum of qty × unit price (GBP) |
| representative_unit_price_gbp | Revenue-weighted average unit price that day |
| transaction_count | Number of contributing invoice lines |
| observed_sales_day | true for source-derived sale days |
| data_source | `REAL_RETAIL_UCI` |

## Splits — train / validation / test

After densification for the selected SKU set, every calendar day in range appears.  
Missing days are filled with `units_sold=0` and `observed_sales_day=false`.

**Interpretation:** zeros are *no recorded transactions*, not proven unconstrained demand or store closure.

| Split | Policy |
|-------|--------|
| test | Final 28 calendar days |
| validation | Previous 28 calendar days |
| train | Earlier densified dates |

SKU selection uses **training-window activity only**.

## Feature columns (modeling)

See `experiments/.../models/feature_schema.json`. Lags and rolling stats use `shift(1)` so the prediction-day target is never included.
