"""
Cleans the marketplace data, loads it into SQLite, runs the SQL analysis, measures
lever impact with difference-in-differences, forecasts weekly rides, reconciles lever
spend against budget, and writes charts, an Excel weekly business review and findings.
"""
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
BLUE, ORANGE, GREY, PINK = "#1F4E79", "#E07B39", "#9AA5B1", "#C2185B"


def style(ax, title):
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def load_queries():
    q, name = {}, None
    for line in (ROOT / "sql" / "analysis.sql").read_text(encoding="utf-8").splitlines():
        if line.startswith("-- name:"):
            name = line.split(":", 1)[1].strip(); q[name] = ""
        elif name:
            q[name] += line + "\n"
    return q


def clean():
    df = pd.read_csv(ROOT / "data" / "marketplace_daily.csv")
    log = [("Rows received", len(df))]
    dup = df.duplicated(); log.append(("Duplicate rows removed", int(dup.sum()))); df = df[~dup].copy()
    miss = df["gross_bookings"].isna()
    fare = (df["gross_bookings"] / df["completed_rides"]).groupby(df["zone"]).transform("median")
    df.loc[miss, "gross_bookings"] = (df.loc[miss, "completed_rides"] * fare[miss]).round(2)
    log.append(("Missing gross bookings filled (zone median fare x rides)", int(miss.sum())))
    log.append(("Rows after cleaning", len(df)))
    return df, log


def did(df, lever_days, launch):
    """Difference-in-differences: lever weekdays vs control weekdays (Wed/Thu), 90 days before vs after launch."""
    d = df.copy(); d["date"] = pd.to_datetime(d["date"]); d["dow"] = d["date"].dt.dayofweek
    launch = pd.Timestamp(launch)
    win = d[(d["date"] >= launch - pd.Timedelta(days=90)) & (d["date"] < launch + pd.Timedelta(days=90))]
    win = win[win["dow"].isin(lever_days + [2, 3])]
    win["treated"] = win["dow"].isin(lever_days); win["post"] = win["date"] >= launch
    daily = win.groupby(["date", "treated", "post"]).agg(rides=("completed_rides", "sum"),
                                                          spend=("promo_spend", "sum"),
                                                          inc=("incentive_spend", "sum")).reset_index()
    m = daily.groupby(["treated", "post"])["rides"].mean()
    lift_pct = ((m[True, True] / m[True, False]) / (m[False, True] / m[False, False]) - 1) * 100
    expected = m[True, False] * (m[False, True] / m[False, False])
    incr_rides_per_day = m[True, True] - expected
    spend_per_day = daily[(daily.treated) & (daily.post)][["spend", "inc"]].sum(axis=1).mean()
    return round(lift_pct, 1), round(incr_rides_per_day), round(spend_per_day / incr_rides_per_day, 2)


def forecast(weekly, horizon=8):
    w = weekly.copy().reset_index(drop=True)
    x = np.arange(len(w))
    def design(xx):
        return np.column_stack([np.ones_like(xx), xx, np.sin(2 * np.pi * xx / 52), np.cos(2 * np.pi * xx / 52)])
    y = w["rides"].to_numpy(float)
    # backtest: train on all but last 8 full weeks
    tr = len(w) - horizon
    beta_bt, *_ = np.linalg.lstsq(design(x[:tr]), y[:tr], rcond=None)
    bt_pred = design(x[tr:]) @ beta_bt
    mape = float(np.mean(np.abs(bt_pred - y[tr:]) / y[tr:]) * 100)
    beta, *_ = np.linalg.lstsq(design(x), y, rcond=None)
    fx = np.arange(len(w), len(w) + horizon)
    fut = design(fx) @ beta
    fut_dates = pd.to_datetime(w["week_start"].iloc[-1]) + pd.to_timedelta(7 * np.arange(1, horizon + 1), unit="D")
    return pd.DataFrame({"week_start": fut_dates, "forecast_rides": fut.round(0)}), round(mape, 1)


def md(df):
    out = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    out += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(out)


def main():
    df, log = clean()
    con = sqlite3.connect(":memory:")
    df.to_sql("marketplace", con, index=False)
    r = {k: pd.read_sql(v, con) for k, v in load_queries().items()}

    weekly = r["weekly_kpis"]
    weekly = weekly[weekly.groupby("week")["week"].transform("size") > 0]
    full = weekly.iloc[1:-1].reset_index(drop=True)          # drop partial first/last weeks
    fc, mape = forecast(full)

    promo = did(df, [0, 1], "2025-06-01")
    inc = did(df, [4, 5], "2025-09-01")
    levers = pd.DataFrame([["Rider promotions (Mon/Tue)", *promo], ["Driver incentives (Fri/Sat)", *inc]],
                          columns=["lever", "ride_lift_pct", "incremental_rides_per_day", "cost_per_incremental_ride"])

    spend = r["monthly_spend"]
    plan = pd.read_csv(ROOT / "data" / "lever_budget_plan.csv").pivot(index="month", columns="program", values="budget").reset_index()
    rec = spend.merge(plan, on="month")
    rec["promo_variance_pct"] = np.where(rec["Rider promotions"] > 0, (rec["promo_actual"] / rec["Rider promotions"] - 1) * 100, np.nan).round(1)
    rec["incentive_variance_pct"] = np.where(rec["Driver incentives"] > 0, (rec["incentive_actual"] / rec["Driver incentives"] - 1) * 100, np.nan).round(1)
    rec = rec.rename(columns={"Rider promotions": "promo_budget", "Driver incentives": "incentive_budget"})
    flagged = rec[(rec["promo_variance_pct"].abs() > 10) | (rec["incentive_variance_pct"].abs() > 10)]

    zones = r["zone_health"]
    FIG.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(pd.to_datetime(full["week_start"]), full["rides"], color=BLUE, lw=1.8, label="Completed rides (weekly)")
    ax.plot(fc["week_start"], fc["forecast_rides"], color=ORANGE, lw=2.2, ls="--", marker="o", ms=3, label=f"8-week forecast (backtest error {mape}%)")
    ax.legend(frameon=False, fontsize=9); ax.set_ylabel("Rides per week")
    style(ax, "Weekly completed rides and forecast")
    fig.tight_layout(); fig.savefig(FIG / "01_weekly_rides_forecast.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(levers["lever"], levers["cost_per_incremental_ride"], color=[BLUE, ORANGE], width=0.5)
    for i, (c_, l) in enumerate(zip(levers["cost_per_incremental_ride"], levers["ride_lift_pct"])):
        ax.text(i, c_ + 0.4, f"${c_:.2f} per extra ride\n(+{l}% rides)", ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("Cost per incremental ride ($)"); ax.set_ylim(0, levers["cost_per_incremental_ride"].max() * 1.35)
    style(ax, "Lever efficiency: cost per incremental ride")
    fig.tight_layout(); fig.savefig(FIG / "02_lever_efficiency.png", dpi=150); plt.close(fig)

    z = zones.sort_values("conversion_pct")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(z["zone"], z["conversion_pct"], color=[ORANGE if v == z["conversion_pct"].min() else BLUE for v in z["conversion_pct"]])
    for i, v in enumerate(z["conversion_pct"]):
        ax.text(v + 0.2, i, f"{v}%", va="center", fontsize=9)
    ax.set_xlim(z["conversion_pct"].min() - 5, 100); ax.set_xlabel("Request-to-ride conversion (%), Aug–Oct 2026")
    style(ax, "Marketplace health by zone"); ax.grid(axis="x", alpha=0.25); ax.grid(axis="y", visible=False)
    fig.tight_layout(); fig.savefig(FIG / "03_zone_conversion.png", dpi=150); plt.close(fig)

    rr = rec[rec["month"] >= "2025-09"]
    fig, ax = plt.subplots(figsize=(9, 4))
    xi = np.arange(len(rr))
    ax.bar(xi - 0.2, rr["promo_variance_pct"], 0.4, color=BLUE, label="Rider promotions")
    ax.bar(xi + 0.2, rr["incentive_variance_pct"], 0.4, color=ORANGE, label="Driver incentives")
    ax.axhline(0, color="#333", lw=0.8); ax.axhspan(-10, 10, color=GREY, alpha=0.12, label="±10% tolerance")
    ax.set_xticks(xi, rr["month"], rotation=45, fontsize=8); ax.set_ylabel("Actual vs budget (%)"); ax.legend(frameon=False, fontsize=8)
    style(ax, "Budget reconciliation: lever spend vs plan")
    fig.tight_layout(); fig.savefig(FIG / "04_budget_variance.png", dpi=150); plt.close(fig)

    last4 = full.tail(4); prev4 = full.iloc[-8:-4]
    wow = round((last4["rides"].sum() / prev4["rides"].sum() - 1) * 100, 1)
    with pd.ExcelWriter(ROOT / "reports" / "weekly_business_review.xlsx", engine="openpyxl") as xl:
        full.tail(12).to_excel(xl, sheet_name="Weekly KPIs", index=False)
        fc.assign(week_start=fc["week_start"].dt.date).to_excel(xl, sheet_name="Forecast", index=False)
        levers.to_excel(xl, sheet_name="Lever Impact", index=False)
        rec.to_excel(xl, sheet_name="Budget Reconciliation", index=False)
        zones.to_excel(xl, sheet_name="Zone Health", index=False)
        for ws in xl.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(12, max(len(str(c.value or "")) for c in col) + 2)

    best = levers.sort_values("cost_per_incremental_ride").iloc[0]; worst = levers.sort_values("cost_per_incremental_ride").iloc[-1]
    low = zones.sort_values("conversion_pct").iloc[0]
    findings = f"""# Weekly Business Review: Rideshare Marketplace (synthetic data)

## Headline
- **Last 4 weeks vs prior 4 weeks:** completed rides {wow:+}%.
- **8-week forecast:** {int(fc['forecast_rides'].sum()):,} rides; model backtest error (MAPE) {mape}%.
- **Most efficient lever:** {best.lever} at **${best.cost_per_incremental_ride:.2f} per incremental ride** (+{best.ride_lift_pct}% rides), versus {worst.lever} at ${worst.cost_per_incremental_ride:.2f}.
- **Weakest zone:** {low.zone}, {low.conversion_pct}% request-to-ride conversion and {low.avg_surge}x average surge, which points to a driver supply gap.
- **Budget:** {len(flagged)} of {len(rec)} months had lever spend more than ±10% off plan.

## Recommendations
1. Shift incremental budget toward the lever with the lower cost per incremental ride, and test a smaller version of the other lever.
2. Target driver incentives at {low.zone} during peak hours to close the supply gap and lower surge.
3. Re-baseline monthly lever budgets using the forecast, so spend tracks volume and stays within ±10% of plan.

## Method
- **Cleaning:** duplicates removed and missing bookings filled from zone median fare ({log[2][1]} rows).
- **SQL:** weekly KPIs, zone health and monthly spend in SQLite (`sql/analysis.sql`).
- **Lever impact:** difference-in-differences comparing lever weekdays with control weekdays (Wed/Thu), 90 days before and after each launch, so growth and seasonality are not counted as lever impact.
- **Forecast:** linear trend plus yearly seasonality, backtested on the last 8 full weeks.
- **Reconciliation:** monthly lever spend vs budget plan, flagged outside ±10%.

## Lever impact
{md(levers)}

## Zone health (Aug–Oct 2026)
{md(zones)}
"""
    (ROOT / "reports" / "findings.md").write_text(findings, encoding="utf-8")
    dq = ["# Data Quality Report", "", "| Check | Result |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in log]
    (ROOT / "reports" / "data_quality_report.md").write_text("\n".join(dq) + "\n", encoding="utf-8")
    print(findings[:1400])


if __name__ == "__main__":
    main()
