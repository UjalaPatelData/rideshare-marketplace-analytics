-- name: weekly_kpis
SELECT date(date, '-6 days', 'weekday 1')                              AS week,
       date(date, '-6 days', 'weekday 1')                              AS week_start,
       SUM(ride_requests)                                              AS requests,
       SUM(completed_rides)                                            AS rides,
       ROUND(100.0 * SUM(completed_rides) / SUM(ride_requests), 1)     AS conversion_pct,
       ROUND(SUM(gross_bookings), 0)                                   AS gross_bookings,
       ROUND(SUM(promo_spend + incentive_spend), 0)                    AS lever_spend
FROM marketplace
GROUP BY week
ORDER BY week;

-- name: zone_health
SELECT zone,
       SUM(completed_rides)                                            AS rides,
       ROUND(100.0 * SUM(completed_rides) / SUM(ride_requests), 1)     AS conversion_pct,
       ROUND(AVG(avg_surge), 2)                                        AS avg_surge,
       ROUND(SUM(completed_rides) / SUM(driver_hours), 2)              AS rides_per_driver_hour
FROM marketplace
WHERE date >= '2026-08-01'
GROUP BY zone
ORDER BY conversion_pct;

-- name: lever_impact
-- Compare lever days with the same weekday before the lever launched (same months)
WITH tagged AS (
  SELECT *,
         CAST(strftime('%w', date) AS INTEGER) AS dow,
         CASE WHEN CAST(strftime('%w', date) AS INTEGER) IN (1,2) THEN 'Rider promotions'
              WHEN CAST(strftime('%w', date) AS INTEGER) IN (5,6) THEN 'Driver incentives' END AS program,
         CASE WHEN CAST(strftime('%w', date) AS INTEGER) IN (1,2) AND date >= '2025-06-01' THEN 1
              WHEN CAST(strftime('%w', date) AS INTEGER) IN (5,6) AND date >= '2025-09-01' THEN 1 ELSE 0 END AS lever_on
  FROM marketplace)
SELECT program,
       lever_on,
       ROUND(AVG(completed_rides), 0)                                  AS avg_rides_per_zone_day,
       ROUND(100.0 * SUM(completed_rides) / SUM(ride_requests), 1)     AS conversion_pct,
       ROUND(SUM(promo_spend + incentive_spend), 0)                    AS spend
FROM tagged
WHERE program IS NOT NULL
GROUP BY program, lever_on
ORDER BY program, lever_on;

-- name: monthly_spend
SELECT strftime('%Y-%m', date)        AS month,
       ROUND(SUM(promo_spend), 0)     AS promo_actual,
       ROUND(SUM(incentive_spend), 0) AS incentive_actual
FROM marketplace
GROUP BY month
ORDER BY month;
