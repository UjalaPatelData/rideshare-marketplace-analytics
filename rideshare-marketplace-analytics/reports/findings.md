# Weekly Business Review: Rideshare Marketplace (synthetic data)

## Headline
- **Last 4 weeks vs prior 4 weeks:** completed rides -3.0%.
- **8-week forecast:** 504,785 rides; model backtest error (MAPE) 1.6%.
- **Most efficient lever:** Rider promotions (Mon/Tue) at **$7.88 per incremental ride** (+10.1% rides), versus Driver incentives (Fri/Sat) at $13.50.
- **Weakest zone:** Suburbs North, 88.2% request-to-ride conversion and 1.1x average surge, which points to a driver supply gap.
- **Budget:** 4 of 22 months had lever spend more than ±10% off plan.

## Recommendations
1. Shift incremental budget toward the lever with the lower cost per incremental ride, and test a smaller version of the other lever.
2. Target driver incentives at Suburbs North during peak hours to close the supply gap and lower surge.
3. Re-baseline monthly lever budgets using the forecast, so spend tracks volume and stays within ±10% of plan.

## Method
- **Cleaning:** duplicates removed and missing bookings filled from zone median fare (15 rows).
- **SQL:** weekly KPIs, zone health and monthly spend in SQLite (`sql/analysis.sql`).
- **Lever impact:** difference-in-differences comparing lever weekdays with control weekdays (Wed/Thu), 90 days before and after each launch, so growth and seasonality are not counted as lever impact.
- **Forecast:** linear trend plus yearly seasonality, backtested on the last 8 full weeks.
- **Reconciliation:** monthly lever spend vs budget plan, flagged outside ±10%.

## Lever impact
| lever | ride_lift_pct | incremental_rides_per_day | cost_per_incremental_ride |
|---|---|---|---|
| Rider promotions (Mon/Tue) | 10.1 | 691 | 7.88 |
| Driver incentives (Fri/Sat) | 5.6 | 442 | 13.5 |

## Zone health (Aug–Oct 2026)
| zone | rides | conversion_pct | avg_surge | rides_per_driver_hour |
|---|---|---|---|---|
| Suburbs North | 79813 | 88.2 | 1.1 | 2.26 |
| East End | 113451 | 95.4 | 1.02 | 2.14 |
| Midtown | 173088 | 96.4 | 1.01 | 2.04 |
| West End | 129185 | 96.4 | 1.01 | 2.02 |
| Airport | 144291 | 96.7 | 1.0 | 1.94 |
| Downtown | 230478 | 96.7 | 1.0 | 2.03 |
