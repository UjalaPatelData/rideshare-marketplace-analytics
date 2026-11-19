"""
Generates a synthetic rideshare marketplace for a fictional city (Jan 2025 - Oct 2026):
hourly demand (ride requests), driver supply, completed rides, fares, and three
marketplace levers: rider promo codes, driver incentives and surge pricing.
Also generates the monthly budget plan for each lever program.
All data is synthetic. No real company or rider data is used.
"""
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(11)
DATA = Path(__file__).resolve().parents[1] / "data"
ZONES = {"Downtown": 1.6, "Airport": 1.0, "Midtown": 1.2, "East End": 0.8, "West End": 0.9, "Suburbs North": 0.6}
SUPPLY = {"Downtown": 1.0, "Airport": 1.05, "Midtown": 1.0, "East End": 0.93, "West End": 1.0, "Suburbs North": 0.82}


def main():
    DATA.mkdir(exist_ok=True)
    days = pd.date_range("2025-01-01", "2026-10-31", freq="D")
    rows = []
    for d in days:
        t = (d - days[0]).days
        trend = 1 + 0.0009 * t                         # steady growth
        season = 1 + 0.12 * np.sin(2 * np.pi * (d.dayofyear - 100) / 365)  # summer peak
        weekday = {4: 1.25, 5: 1.35, 6: 0.9}.get(d.dayofweek, 1.0)          # Fri/Sat peaks
        promo_on = d.dayofweek in (0, 1) and d >= pd.Timestamp("2025-06-01")  # Mon/Tue rider promos
        incentive_on = d.dayofweek in (4, 5) and d >= pd.Timestamp("2025-09-01")  # Fri/Sat driver incentives
        for z, w in ZONES.items():
            base = 900 * w * trend * season * weekday
            requests = RNG.poisson(base * (1.12 if promo_on else 1.0))
            supply_hours = base / weekday * weekday ** 0.15 * 0.5 * SUPPLY[z] * (1.15 if incentive_on else 1.0) * RNG.normal(1, 0.06)
            cap = supply_hours * 2.3
            completion = min(0.97, cap / max(requests, 1)) * RNG.normal(1, 0.015)
            completion = float(np.clip(completion, 0.6, 0.98))
            completed = int(requests * completion)
            surge = float(np.clip(1 + (requests / cap - 1) * 0.8, 1, 2.2)) if requests > cap else 1.0
            avg_fare = 16.5 * (1.35 if z == "Airport" else 1) * surge * RNG.normal(1, 0.03)
            gross = completed * avg_fare
            promo_cost = completed * 0.18 * 4.0 if promo_on else 0.0      # 18% of rides use a $4 promo
            incentive_cost = supply_hours * 1.5 if incentive_on else 0.0  # $1.50/hr driver boost
            rows.append((d.date(), z, requests, completed, round(supply_hours, 1), round(surge, 2),
                         round(gross, 2), round(promo_cost, 2), round(incentive_cost, 2)))
    df = pd.DataFrame(rows, columns=["date", "zone", "ride_requests", "completed_rides", "driver_hours",
                                     "avg_surge", "gross_bookings", "promo_spend", "incentive_spend"])
    # data quality issues on purpose
    df = pd.concat([df, df.sample(40, random_state=1)])
    df.loc[df.sample(15, random_state=2).index, "gross_bookings"] = np.nan
    df.to_csv(DATA / "marketplace_daily.csv", index=False)

    # monthly budget plan per lever: finance plans close to expected spend, with a few misses
    d2 = df.drop_duplicates().copy(); d2["month"] = pd.to_datetime(d2["date"]).dt.to_period("M").astype(str)
    act = d2.groupby("month")[["promo_spend", "incentive_spend"]].sum()
    miss = {"2025-12": 1.22, "2026-03": 0.80, "2026-07": 1.18}
    plan = []
    for m, row in act.iterrows():
        for prog, col in (("Rider promotions", "promo_spend"), ("Driver incentives", "incentive_spend")):
            if row[col] == 0:
                plan.append((m, prog, 0)); continue
            factor = miss.get(m, RNG.normal(1, 0.04)) if prog == "Driver incentives" or m != "2026-03" else RNG.normal(1, 0.04)
            plan.append((m, prog, round(row[col] / factor, -2)))
    pd.DataFrame(plan, columns=["month", "program", "budget"]).to_csv(DATA / "lever_budget_plan.csv", index=False)
    print(f"Wrote {len(df):,} daily zone rows and the lever budget plan to data/")


if __name__ == "__main__":
    main()
