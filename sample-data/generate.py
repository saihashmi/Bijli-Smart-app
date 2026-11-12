"""Generate synthetic, deliberately messy sample files for trying Bijli Smart.

    python sample-data/generate.py

The values are synthetic (random but realistic shapes); they are only for demos and tests.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent
rng = np.random.default_rng(42)


def household_hourly() -> pd.DataFrame:
    idx = pd.date_range("2025-06-01", "2025-08-29 23:00", freq="h")
    hour = idx.hour
    base = 0.35  # fridge, router, standby
    evening = np.where((hour >= 18) & (hour < 23), 1.4, 0)
    morning = np.where((hour >= 6) & (hour < 9), 0.6, 0)
    ac = np.where((hour >= 13) & (hour < 17), 0.9, 0) + np.where((hour >= 22) | (hour < 3), 0.8, 0)
    heat = np.linspace(0.8, 1.2, len(idx))  # summer gets hotter: usage trends up
    kwh = (base + (evening + morning + ac) * heat) * rng.uniform(0.8, 1.2, len(idx))
    weekend = idx.dayofweek >= 5
    kwh = np.where(weekend & (hour >= 10) & (hour < 18), kwh + 0.5, kwh)
    df = pd.DataFrame({"Reading Time": idx, "Energy (kWh)": kwh.round(3)})
    # A faulty-appliance spike over two days
    spike = (df["Reading Time"] >= "2025-07-14") & (df["Reading Time"] < "2025-07-16")
    df.loc[spike, "Energy (kWh)"] += 2.5
    df["Reading Time"] = df["Reading Time"].dt.strftime("%Y-%m-%d %H:%M")

    # --- make it messy ---
    df = df.astype({"Energy (kWh)": object})
    for i in rng.choice(len(df), 25, replace=False):
        df.at[i, "Energy (kWh)"] = None
    for i in rng.choice(len(df), 40, replace=False):
        df.at[i, "Energy (kWh)"] = f"{df.at[i, 'Energy (kWh)']} kWh" if df.at[i, "Energy (kWh)"] is not None else None
    for i in rng.choice(len(df), 4, replace=False):
        df.at[i, "Energy (kWh)"] = -1.0
    for i in rng.choice(len(df), 3, replace=False):
        df.at[i, "Reading Time"] = "n/a"
    # dd/mm/yyyy dates on part of the file (a different export)
    tail = df.index[-200:]
    df.loc[tail, "Reading Time"] = pd.to_datetime(df.loc[tail, "Reading Time"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")
    df.loc[tail[tail % 50 == 0], "Reading Time"] = "n/a"
    dupes = df.sample(12, random_state=1)
    df = pd.concat([df, dupes]).sort_index(kind="stable").reset_index(drop=True)
    df["Meter"] = np.where(rng.random(len(df)) < 0.01, " Home ", "Home")
    return df


def office_bills() -> pd.DataFrame:
    rows = []
    months = pd.period_range("2024-01", "2025-09", freq="M")
    for site, scale in (("Head Office", 4200), ("Warehouse", 2600), ("Retail Branch", 1500)):
        for m in months:
            seasonal = 1 + 0.45 * np.sin((m.month - 4) / 12 * 2 * np.pi)  # summer peak
            units = scale * seasonal * rng.uniform(0.9, 1.1)
            rate = 52 if m.year == 2024 else 61
            rows.append({"Billing Month": m.strftime("%b-%Y"), "Branch": site,
                         "Units Consumed": round(units), "Bill Amount (Rs)": f"Rs {units * rate:,.0f}"})
    df = pd.DataFrame(rows)
    df.loc[5, "Units Consumed"] = None
    df.loc[17, "Bill Amount (Rs)"] = ""
    df = pd.concat([df, df.iloc[[3, 30]]]).reset_index(drop=True)
    return df


if __name__ == "__main__":
    household_hourly().to_csv(OUT / "household_hourly_messy.csv", index=False)
    office_bills().to_excel(OUT / "office_monthly_bills.xlsx", index=False, sheet_name="Bills")
    print("Wrote", OUT / "household_hourly_messy.csv", "and", OUT / "office_monthly_bills.xlsx")
