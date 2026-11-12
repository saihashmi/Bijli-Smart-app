"""All analytics are computed here, from the cleaned rows, with pandas/numpy.

Nothing in this module estimates or invents data: every figure traces back to the uploaded file
and the settings the user entered (tariff, peak hours).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .jsonutil import jsonable, r

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _frame(df: pd.DataFrame, mapping: dict[str, Any]) -> pd.DataFrame:
    f = pd.DataFrame({
        "ts": pd.to_datetime(df[mapping["timestamp"]]),
        "kwh": pd.to_numeric(df[mapping["consumption"]], errors="coerce"),
    })
    if mapping.get("cost") and mapping["cost"] in df:
        f["cost"] = pd.to_numeric(df[mapping["cost"]], errors="coerce")
    if mapping.get("category") and mapping["category"] in df:
        f["category"] = df[mapping["category"]].fillna("Unspecified").astype(str)
    return f.dropna(subset=["ts", "kwh"]).sort_values("ts").reset_index(drop=True)


def _granularity(ts: pd.Series) -> dict[str, Any]:
    uniq = ts.drop_duplicates().sort_values()
    if len(uniq) < 2:
        return {"label": "single", "median_minutes": None, "intraday": False}
    minutes = float(uniq.diff().dropna().dt.total_seconds().median() / 60)
    if minutes < 60 * 20:
        label = "hourly" if minutes >= 50 else "sub-hourly"
    elif minutes < 60 * 24 * 5:
        label = "daily"
    elif minutes < 60 * 24 * 20:
        label = "weekly"
    else:
        label = "monthly"
    return {"label": label, "median_minutes": r(minutes, 1), "intraday": minutes < 60 * 20}


def analyze(df: pd.DataFrame, mapping: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    f = _frame(df, mapping)
    currency = settings.get("currency") or "Rs"
    tariff = settings.get("tariff_per_kwh")
    tariff = float(tariff) if tariff not in (None, "") else None
    peak_start = int(settings.get("peak_start_hour", 18))
    peak_end = int(settings.get("peak_end_hour", 22))
    reduction_pct = float(settings.get("reduction_target_pct", 10))

    if f.empty:
        return {"empty": True, "message": "No rows with both a valid date and a consumption value.", "facts": []}

    gran = _granularity(f["ts"])
    has_cost_col = "cost" in f and f["cost"].notna().any()

    # Cost: prefer the actual billed amounts; otherwise use the tariff the user entered.
    if has_cost_col:
        cost_source = "file"
    elif tariff is not None:
        f["cost"] = f["kwh"] * tariff
        cost_source = "tariff"
    else:
        cost_source = None

    total_kwh = float(f["kwh"].sum())
    total_cost = float(f["cost"].sum()) if cost_source else None
    rate = None
    if cost_source == "file":
        billed = f.dropna(subset=["cost"])
        rate = float(billed["cost"].sum() / billed["kwh"].sum()) if billed["kwh"].sum() > 0 else None
    elif cost_source == "tariff":
        rate = tariff

    # ---- time series ----
    f["date"] = f["ts"].dt.normalize()
    agg = {"kwh": "sum"} | ({"cost": "sum"} if cost_source else {})
    daily = f.groupby("date").agg(agg).reset_index()
    monthly = f.groupby(f["ts"].dt.to_period("M")).agg(agg).reset_index().rename(columns={"ts": "month"})
    monthly["change_pct"] = monthly["kwh"].pct_change() * 100

    start, end = f["ts"].min(), f["ts"].max()
    if gran["label"] == "monthly":
        # A monthly bill dated the 1st covers the whole month.
        end = (end.to_period("M").end_time).floor("s")
    span_days = int((end.normalize() - start.normalize()).days) + 1
    days_with_data = int(daily["date"].nunique())

    series_for_stats = daily if gran["label"] in ("hourly", "sub-hourly", "daily") else None
    if gran["label"] == "monthly":
        avg_daily = total_kwh / span_days if span_days else None  # bills: spread over the covered span
    else:
        avg_daily = float(daily["kwh"].mean())

    summary: dict[str, Any] = {
        "records": int(len(f)),
        "start": jsonable(start),
        "end": jsonable(end),
        "span_days": span_days,
        "days_with_data": days_with_data,
        "granularity": gran["label"],
        "total_kwh": r(total_kwh),
        "avg_daily_kwh": r(avg_daily),
        "total_cost": r(total_cost),
        "effective_rate": r(rate, 3),
        "cost_source": cost_source,
        "currency": currency,
    }
    if series_for_stats is not None and len(daily):
        peak = daily.loc[daily["kwh"].idxmax()]
        low = daily.loc[daily["kwh"].idxmin()]
        summary["peak_day"] = {"date": jsonable(peak["date"].date()), "kwh": r(peak["kwh"])}
        summary["lowest_day"] = {"date": jsonable(low["date"].date()), "kwh": r(low["kwh"])}
    if len(monthly):
        pk = monthly.loc[monthly["kwh"].idxmax()]
        summary["peak_month"] = {"month": str(pk["month"]), "kwh": r(pk["kwh"])}

    # ---- profiles ----
    weekday = None
    if gran["label"] in ("hourly", "sub-hourly", "daily") and days_with_data >= 7:
        d = daily.copy()
        d["wd"] = d["date"].dt.dayofweek
        w = d.groupby("wd")["kwh"].mean()
        weekday = [{"day": WEEKDAYS[i], "avg_kwh": r(w.get(i))} for i in range(7) if i in w.index]

    hourly = None
    peak_share = None
    baseload = None
    if gran["intraday"]:
        f["hour"] = f["ts"].dt.hour
        per_day_hour = f.groupby(["date", "hour"])["kwh"].sum().reset_index()
        h = per_day_hour.groupby("hour")["kwh"].mean()
        hourly = [{"hour": int(i), "avg_kwh": r(v, 3)} for i, v in h.items()]
        in_peak = f["hour"].between(peak_start, peak_end - 1) if peak_end > peak_start else (
            (f["hour"] >= peak_start) | (f["hour"] < peak_end))
        peak_kwh = float(f.loc[in_peak, "kwh"].sum())
        hours_in_window = (peak_end - peak_start) % 24 or 24
        peak_share = {
            "window": f"{peak_start:02d}:00–{peak_end:02d}:00",
            "hours": hours_in_window,
            "kwh": r(peak_kwh),
            "share_pct": r(peak_kwh / total_kwh * 100 if total_kwh else None, 1),
            "even_share_pct": r(hours_in_window / 24 * 100, 1),
        }
        # Always-on load: the typical lowest hourly draw, i.e. what runs even when nobody is using power.
        hour_totals = f.set_index("ts")["kwh"].resample("h").sum(min_count=1).dropna()
        if len(hour_totals) >= 48:
            base_kw = float(hour_totals.groupby(hour_totals.index.normalize()).min().median())
            base_kwh = base_kw * len(hour_totals)
            baseload = {
                "kw": r(base_kw, 3),
                "kwh": r(base_kwh),
                "share_pct": r(base_kwh / total_kwh * 100 if total_kwh else None, 1),
                "hours_observed": int(len(hour_totals)),
            }

    # ---- categories ----
    categories = None
    if "category" in f:
        c = f.groupby("category").agg(agg).sort_values("kwh", ascending=False).reset_index()
        c["share_pct"] = c["kwh"] / total_kwh * 100 if total_kwh else np.nan
        categories = [
            {"category": row["category"], "kwh": r(row["kwh"]), "share_pct": r(row["share_pct"], 1),
             **({"cost": r(row["cost"])} if cost_source else {})}
            for _, row in c.iterrows()
        ]

    # ---- trend ----
    trend = None
    base = daily if series_for_stats is not None else monthly.rename(columns={"month": "date"})
    if len(base) >= 4:
        y = base["kwh"].to_numpy(dtype=float)
        x = np.arange(len(y), dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        half = len(y) // 2
        first, second = float(y[:half].mean()), float(y[half:].mean())
        unit = "day" if series_for_stats is not None else "month"
        trend = {
            "unit": unit,
            "slope_kwh_per_period": r(slope, 3),
            "first_half_avg": r(first),
            "second_half_avg": r(second),
            "change_pct": r((second - first) / first * 100 if first else None, 1),
            "direction": "rising" if second > first * 1.05 else "falling" if second < first * 0.95 else "stable",
        }

    # ---- anomalies (robust z-score on daily totals) ----
    anomalies: list[dict[str, Any]] = []
    excess_kwh = 0.0
    if series_for_stats is not None and len(daily) >= 10:
        v = daily["kwh"]
        med = float(v.median())
        mad = float((v - med).abs().median())
        if mad > 0:
            z = 0.6745 * (v - med) / mad
            flagged = daily[z.abs() > 3.5]
        else:
            q1, q3 = v.quantile(0.25), v.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                flagged = daily[(v > q3 + 1.5 * iqr) | (v < q1 - 1.5 * iqr)]
            else:
                # Almost every day is identical: flag days more than 50% away from that level.
                flagged = daily[(v - med).abs() > 0.5 * abs(med)] if med else daily[v != med]
        for _, row in flagged.sort_values("kwh", ascending=False).iterrows():
            dev = (row["kwh"] - med) / med * 100 if med else None
            if row["kwh"] > med:
                excess_kwh += float(row["kwh"] - med)
            anomalies.append({
                "date": jsonable(row["date"].date()),
                "kwh": r(row["kwh"]),
                "typical_kwh": r(med),
                "deviation_pct": r(dev, 1),
                "direction": "high" if row["kwh"] > med else "low",
            })

    # ---- savings scenarios (arithmetic on the figures above) ----
    savings = []
    scen_kwh = total_kwh * reduction_pct / 100
    savings.append({
        "id": "reduction_target",
        "title": f"Cut overall use by {_fmt(reduction_pct, 1)}%",
        "kwh": r(scen_kwh),
        "cost": r(scen_kwh * rate) if rate else None,
        "basis": f"{_fmt(reduction_pct, 1)}% of the {_fmt(total_kwh)} kWh in this file.",
    })
    if excess_kwh > 0:
        savings.append({
            "id": "anomaly_days",
            "title": "Bring unusually high days back to a typical day",
            "kwh": r(excess_kwh),
            "cost": r(excess_kwh * rate) if rate else None,
            "basis": "Sum of consumption above the median day on days flagged as anomalies.",
        })
    if baseload and baseload["kw"] and baseload["kw"] > 0:
        half_base = (baseload["kwh"] or 0) * 0.25
        savings.append({
            "id": "baseload",
            "title": "Reduce always-on load by a quarter",
            "kwh": r(half_base),
            "cost": r(half_base * rate) if rate else None,
            "basis": f"25% of the {_fmt(baseload['kwh'])} kWh drawn by the {_fmt(baseload['kw'], 3)} kW always-on load.",
        })
    if categories and len(categories) > 1:
        top = categories[0]
        cut = (top["kwh"] or 0) * 0.2
        savings.append({
            "id": "top_category",
            "title": f"Cut '{top['category']}' use by 20%",
            "kwh": r(cut),
            "cost": r(cut * rate) if rate else None,
            "basis": f"20% of the {_fmt(top['kwh'])} kWh used by the largest category.",
        })

    result = {
        "empty": False,
        "summary": summary,
        "daily": [{"date": jsonable(d.date()), "kwh": r(k, 3), **({"cost": r(cst)} if cost_source else {})}
                  for d, k, cst in zip(daily["date"], daily["kwh"], daily["cost"] if cost_source else [None] * len(daily))],
        "monthly": [{"month": str(m), "kwh": r(k), "change_pct": r(ch, 1), **({"cost": r(cst)} if cost_source else {})}
                    for m, k, ch, cst in zip(monthly["month"], monthly["kwh"], monthly["change_pct"],
                                             monthly["cost"] if cost_source else [None] * len(monthly))],
        "weekday": weekday,
        "hourly": hourly,
        "peak_hours": peak_share,
        "baseload": baseload,
        "categories": categories,
        "trend": trend,
        "anomalies": anomalies,
        "savings": savings,
        "settings": {"currency": currency, "tariff_per_kwh": tariff, "peak_start_hour": peak_start,
                     "peak_end_hour": peak_end, "reduction_target_pct": reduction_pct},
    }
    result["facts"] = build_facts(result)
    return result


def _fmt(v: Any, digits: int = 2) -> str:
    if v is None:
        return "n/a"
    f = float(v)
    if abs(f) >= 1000:
        return f"{f:,.0f}"
    out = f"{f:.{digits}f}"
    return out.rstrip("0").rstrip(".") if "." in out else out


def build_facts(a: dict[str, Any]) -> list[dict[str, Any]]:
    """Plain-language statements generated from computed values. These are the only facts the AI may use."""
    s = a["summary"]
    cur = s["currency"]
    facts: list[dict[str, Any]] = []

    def add(fid: str, category: str, text: str, values: dict[str, Any], severity: str = "info") -> None:
        facts.append({"id": fid, "category": category, "text": text, "values": values, "severity": severity})

    cost_txt = f", costing {cur} {_fmt(s['total_cost'])}" if s.get("total_cost") is not None else ""
    add("total", "summary",
        f"{_fmt(s['total_kwh'])} kWh were used between {s['start'][:10]} and {s['end'][:10]} "
        f"({s['span_days']} days){cost_txt}.",
        {"total_kwh": s["total_kwh"], "total_cost": s.get("total_cost"), "span_days": s["span_days"]})
    if s.get("avg_daily_kwh") is not None:
        add("avg_daily", "summary", f"Average use was {_fmt(s['avg_daily_kwh'])} kWh per day.",
            {"avg_daily_kwh": s["avg_daily_kwh"]})
    if s.get("effective_rate") is not None:
        src = "billed amounts in the file" if s["cost_source"] == "file" else "the tariff you entered"
        add("rate", "cost", f"The effective rate is {cur} {_fmt(s['effective_rate'], 3)} per kWh, based on {src}.",
            {"effective_rate": s["effective_rate"]})
    if s.get("peak_day"):
        add("peak_day", "pattern",
            f"The highest-use day was {s['peak_day']['date']} at {_fmt(s['peak_day']['kwh'])} kWh.",
            {"peak_day_kwh": s["peak_day"]["kwh"]})
    if s.get("peak_month") and len(a["monthly"]) > 1:
        add("peak_month", "pattern",
            f"The highest-use month was {s['peak_month']['month']} at {_fmt(s['peak_month']['kwh'])} kWh.",
            {"peak_month_kwh": s["peak_month"]["kwh"]})

    t = a.get("trend")
    if t and t.get("change_pct") is not None:
        sev = "warning" if t["direction"] == "rising" else "positive" if t["direction"] == "falling" else "info"
        add("trend", "trend",
            f"Consumption is {t['direction']}: the average per {t['unit']} went from {_fmt(t['first_half_avg'])} kWh "
            f"in the first half of the period to {_fmt(t['second_half_avg'])} kWh in the second half "
            f"({'+' if t['change_pct'] > 0 else ''}{_fmt(t['change_pct'], 1)}%).",
            {"first_half_avg": t["first_half_avg"], "second_half_avg": t["second_half_avg"], "change_pct": t["change_pct"]},
            sev)

    m = a["monthly"]
    if len(m) >= 2 and m[-1].get("change_pct") is not None:
        last = m[-1]
        add("last_month", "trend",
            f"{last['month']} used {_fmt(last['kwh'])} kWh, {'+' if last['change_pct'] > 0 else ''}"
            f"{_fmt(last['change_pct'], 1)}% compared with {m[-2]['month']}.",
            {"last_month_kwh": last["kwh"], "change_pct": last["change_pct"]},
            "warning" if last["change_pct"] > 10 else "info")

    ph = a.get("peak_hours")
    if ph and ph.get("share_pct") is not None:
        sev = "warning" if ph["share_pct"] > (ph["even_share_pct"] or 0) * 1.3 else "info"
        add("peak_hours", "pattern",
            f"{_fmt(ph['share_pct'], 1)}% of consumption fell in the {ph['window']} peak window, which covers "
            f"{_fmt(ph['even_share_pct'], 1)}% of the day's hours.",
            {"peak_share_pct": ph["share_pct"], "window_share_of_day_pct": ph["even_share_pct"]}, sev)

    b = a.get("baseload")
    if b and b.get("share_pct") is not None:
        add("baseload", "pattern",
            f"An always-on load of about {_fmt(b['kw'], 3)} kW accounts for {_fmt(b['share_pct'], 1)}% of consumption "
            f"({_fmt(b['kwh'])} kWh).",
            {"baseload_kw": b["kw"], "baseload_share_pct": b["share_pct"], "baseload_kwh": b["kwh"]},
            "warning" if b["share_pct"] > 30 else "info")

    wd = a.get("weekday")
    if wd and len(wd) == 7:
        hi = max(wd, key=lambda x: x["avg_kwh"] or 0)
        lo = min(wd, key=lambda x: x["avg_kwh"] or 0)
        add("weekday", "pattern",
            f"{hi['day']} is the heaviest day of the week on average ({_fmt(hi['avg_kwh'])} kWh) and "
            f"{lo['day']} the lightest ({_fmt(lo['avg_kwh'])} kWh).",
            {"weekday_high_kwh": hi["avg_kwh"], "weekday_low_kwh": lo["avg_kwh"]})

    cats = a.get("categories")
    if cats and len(cats) > 1:
        top = cats[0]
        add("top_category", "breakdown",
            f"'{top['category']}' is the largest consumer with {_fmt(top['kwh'])} kWh, "
            f"{_fmt(top['share_pct'], 1)}% of the total.",
            {"top_category_kwh": top["kwh"], "top_category_share_pct": top["share_pct"]})

    an = a.get("anomalies") or []
    if an:
        highs = [x for x in an if x["direction"] == "high"]
        add("anomalies", "anomaly",
            f"{len(an)} day(s) were unusual compared with a typical day of {_fmt(an[0]['typical_kwh'])} kWh"
            + (f"; the largest was {highs[0]['date']} at {_fmt(highs[0]['kwh'])} kWh "
               f"({'+' if highs[0]['deviation_pct'] > 0 else ''}{_fmt(highs[0]['deviation_pct'], 1)}%)." if highs else "."),
            {"anomaly_count": len(an), "typical_kwh": an[0]["typical_kwh"],
             **({"largest_anomaly_kwh": highs[0]["kwh"], "largest_deviation_pct": highs[0]["deviation_pct"]} if highs else {})},
            "warning")

    for sv in a.get("savings") or []:
        cost = f" (about {cur} {_fmt(sv['cost'])})" if sv.get("cost") is not None else ""
        add(f"saving_{sv['id']}", "saving", f"{sv['title']}: saves {_fmt(sv['kwh'])} kWh{cost}. {sv['basis']}",
            {"kwh": sv["kwh"], "cost": sv.get("cost")}, "positive")
    return facts
