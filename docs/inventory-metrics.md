# Inventory metrics

All money is integer paise. Display divides by 100 and formats rupees. Aggregate ratios use totals, never the mean of SKU ratios.

Historical series come from `inventory_daily_snapshots` for the latest complete analytics run. Live stock comes from `products.stock_on_hand`. Receiving a reorder updates live stock and does not rewrite snapshots.

## Conservation

For each product-day:

`closing_stock = opening_stock + received_units + returned_units + adjustment_units - sold_units - writeoff_units`

The next day's opening stock equals this closing stock. Closing stock is never negative.

`sales.units` stay recorded demand. `sold_units` are fulfilled units. `unmet_demand_units = demand_units - sold_units`. Unfulfilled demand is excluded from units sold, COGS, and revenue.

## Valuation

`closing_value_paise = closing_stock * unit_cost_paise`

`cogs_paise = sold_units * unit_cost_paise`

`revenue_paise` is fulfilled units times the price stored on that sales row.

The demo cost model is the fixed catalog `unit_cost_paise`. It is not a moving average and not a retail valuation.

## Period

The default window is the snapshot calendar: 2025-11-02 through 2026-11-01 (365 days) when analytics were built with seed 42. Filters (`from`, `to`, `year`, `month`, `category`, `supplier`, `product`) apply to every period metric. An empty window returns null ratios rather than zero or infinity.

Period-end inventory is the closing stock and value on the last snapshot date inside the window.

## Current inventory value

`SUM(stock_on_hand * unit_cost_paise)` over active products matching the category, supplier, and product filters. Date filters do not change this live figure. The overview also returns the period-end snapshot value separately.

## Available stock

`SUM(stock_on_hand)` for the same live filter. Units stay separate from value.

## Inventory turnover

`period COGS / average of daily total closing inventory value`

The average is the mean of the business-wide closing value on each day in the window. It is not the average of SKU turnovers and it is not annualized when the chart shows one month.

Turnover is null when the average inventory value is 0.

The gauge reference target of 6 is a documented demo planning mark. It is not an industry benchmark. The arc caps at 12. The number underneath is the calculated turnover. On this grocery panel that number is about 54 for the full year, which is consistent with a few days of stock cover.

## Days inventory outstanding

`DIO = snapshot days in the window / inventory turnover`

DIO is null when turnover is null or 0. DIO is an accounting cover measure. It is not forecast-based days of supply (`forecast_28d / 28` against on-hand stock).

## Inventory-to-sales ratio

`period-end inventory value / period fulfilled sales revenue`

Null when fulfilled revenue is 0. The ratio is not annualized.

## Inventory movement

Opening units and value are the first day's opening stock in the window. Receipts, fulfilled sales, returns, adjustments, and write-offs are sums across the window. Closing units and value are the last day's closing balance. The API reports whether units and value each conserve under the identity above. Value conservation uses the same fixed unit cost, so a unit identity implies a value identity.

## Inventory value trend

Month-end closing value, plus the previous month's value, absolute change, and percentage change. Percentage change is omitted when the previous value is 0 or missing. Tooltips also show that month's fulfilled revenue and inventory-to-sales ratio when revenue is positive.

## Rankings

Top products can be ordered by period-end inventory value, period-end quantity, fulfilled revenue, or fulfilled volume. The page toggle switches value and quantity. Labels include the product name and SKU.

## Category contribution

Sum of period-end inventory value and fulfilled revenue by category, using the same product set as the rankings.

## Excess inventory proxy

Current on-hand units above 45 days of forecast daily demand. Daily demand is `forecast_28d / 28` from the risk cache. Products with no positive forecast are excluded. The proxy ignores the date filter because it describes live stock. It is not lot age and not an expiry write-off.

## Slow-moving indicators

For the 30 and 90 snapshot days ending on the period end (not clipped by a month filter):

- fulfilled units
- current stock and stock value
- forecast days of supply
- days since the last sales row with demand greater than zero
- excess units from the proxy above

Suggested actions are deterministic templates from those flags. No expiration date is shown. Lot age is not claimed.

## ABC

Products are sorted by fulfilled revenue descending, with product id as the tie break.

- A: cumulative revenue through 80 percent
- B: the next band through 95 percent
- C: the remainder, including zero-revenue products

A product that crosses a threshold stays in the class it crosses into. These thresholds are constants in `inventory_analytics.py`. This is not a machine-learning model.

## XYZ

Population coefficient of variation of daily demand, including zero-demand days.

- X: CV below 0.5
- Y: CV below 1.0
- Z: CV at or above 1.0, or a zero mean

## Supplier figures

- Modeled lead time and catalog delivery reliability are supplier parameters from the synthetic catalog. Reliability is not a measured on-time rate.
- Simulated on-time rate and average delay count reconstructed replenishment receipts whose drawn delay was zero. Reconciliation receipts are excluded.
- When a category or product filter is active, receipt counts and open reorder quantity use the same product filter as the stock value.
- The UI labels the rate as simulated.

## Reorder calendar dates

- Actual received: `reviewed_at` on a received reorder.
- Planned arrival: the reorder's expected arrival when one was stored. No date is invented.
- Predicted arrival: a recommendation's expected arrival, or the demo date plus forecast days of supply for a high-risk watch that has no recommendation date.
