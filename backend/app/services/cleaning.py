"""Data-quality profiling, deterministic cleaning suggestions, and the cleaning pipeline.

Every count reported here is computed from the uploaded rows. Suggestions are rule-based;
the optional AI layer may only explain or prioritise them, never invent new ones.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .ingest import parse_datetime, parse_numeric
from .jsonutil import jsonable, r

# Action id -> (title, group). Actions in the same exclusive group cannot be combined.
ACTIONS: dict[str, dict[str, Any]] = {
    "trim_text": {"title": "Trim whitespace in text cells", "group": None},
    "drop_empty_rows": {"title": "Remove completely empty rows", "group": None},
    "drop_duplicates": {"title": "Remove exact duplicate rows", "group": None},
    "drop_invalid_dates": {"title": "Remove rows with missing or unreadable dates", "group": None},
    "cumulative_to_delta": {"title": "Convert cumulative meter readings into usage per period", "group": None},
    "remove_negative": {"title": "Remove rows with negative consumption", "group": None},
    "drop_missing_consumption": {"title": "Remove rows with missing consumption", "group": "missing"},
    "interpolate_missing_consumption": {"title": "Fill missing consumption by time interpolation", "group": "missing"},
    "dedupe_timestamps": {"title": "Keep one row per timestamp (and category)", "group": None},
    "remove_outliers": {"title": "Remove extreme outliers (beyond 3× IQR)", "group": None},
    "sort_by_date": {"title": "Sort rows by date", "group": None},
}

# Fixed pipeline order, independent of the order the user ticked boxes.
PIPELINE_ORDER = list(ACTIONS.keys())


@dataclass
class Typed:
    ts: pd.Series | None
    kwh: pd.Series | None
    cost: pd.Series | None


def _typed(df: pd.DataFrame, mapping: dict[str, Any]) -> Typed:
    dayfirst = bool(mapping.get("dayfirst", True))
    ts_col, kwh_col, cost_col = mapping.get("timestamp"), mapping.get("consumption"), mapping.get("cost")
    return Typed(
        ts=parse_datetime(df[ts_col], dayfirst) if ts_col in df else None,
        kwh=parse_numeric(df[kwh_col]) if kwh_col in df else None,
        cost=parse_numeric(df[cost_col]) if cost_col in df else None,
    )


def _blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip() == "")


def _text_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if df[c].dtype == object]


def _iqr_bounds(values: pd.Series, k: float = 3.0) -> tuple[float, float] | None:
    v = values.dropna()
    if len(v) < 8:
        return None
    q1, q3 = v.quantile(0.25), v.quantile(0.75)
    iqr = q3 - q1
    if iqr <= 0:
        return None
    return float(q1 - k * iqr), float(q3 + k * iqr)


def looks_cumulative(ts: pd.Series, kwh: pd.Series) -> bool:
    """Meter readings that only ever go up (e.g. 10234, 10251, 10270 ...)."""
    frame = pd.DataFrame({"ts": ts, "kwh": kwh}).dropna().sort_values("ts")
    if len(frame) < 6:
        return False
    diffs = frame["kwh"].diff().dropna()
    if (diffs >= 0).mean() < 0.97:
        return False
    # Cumulative counters are large relative to the step between readings.
    median_step = diffs[diffs > 0].median() if (diffs > 0).any() else 0
    return bool(median_step and frame["kwh"].median() > 20 * median_step)


def profile(df: pd.DataFrame, mapping: dict[str, Any]) -> dict[str, Any]:
    t = _typed(df, mapping)
    n = len(df)
    columns = []
    for c in df.columns:
        s = df[c]
        blank = _blank(s)
        info: dict[str, Any] = {
            "name": c,
            "role": next((role for role in ("timestamp", "consumption", "cost", "category") if mapping.get(role) == c), None),
            "missing": int(blank.sum()),
            "missing_pct": r(blank.mean() * 100 if n else 0, 1),
            "unique": int(s[~blank].astype(str).nunique()),
            "sample": [jsonable(v) for v in s[~blank].astype(str).head(3).tolist()],
        }
        nums = parse_numeric(s[~blank]) if (~blank).any() else pd.Series(dtype=float)
        num_rate = float(nums.notna().mean()) if len(nums) else 0.0
        if info["role"] == "timestamp" and t.ts is not None:
            valid = t.ts[~blank]
            info.update(
                kind="datetime",
                unparseable=int(valid.isna().sum()),
                min=jsonable(t.ts.min()),
                max=jsonable(t.ts.max()),
            )
        elif num_rate >= 0.6 or info["role"] in ("consumption", "cost"):
            info.update(
                kind="numeric",
                unparseable=int(nums.isna().sum()),
                min=r(nums.min()),
                max=r(nums.max()),
                mean=r(nums.mean()),
                negatives=int((nums < 0).sum()),
            )
        else:
            info.update(kind="text", whitespace_issues=int((s[~blank].astype(str) != s[~blank].astype(str).str.strip()).sum()))
        columns.append(info)

    empty_rows = int(df.apply(_blank).all(axis=1).sum()) if n else 0
    duplicate_rows = int(df.duplicated().sum()) if n else 0
    return {
        "rows": n,
        "columns_count": df.shape[1],
        "empty_rows": empty_rows,
        "duplicate_rows": duplicate_rows,
        "columns": columns,
        "suggestions": suggest(df, mapping, t),
    }


def suggest(df: pd.DataFrame, mapping: dict[str, Any], t: Typed | None = None) -> list[dict[str, Any]]:
    t = t or _typed(df, mapping)
    out: list[dict[str, Any]] = []

    def add(action: str, affected: int, reason: str, recommended: bool = True) -> None:
        out.append({
            "id": action,
            "title": ACTIONS[action]["title"],
            "group": ACTIONS[action]["group"],
            "affected_rows": int(affected),
            "reason": reason,
            "recommended": recommended,
        })

    text_cols = _text_columns(df)
    ws = 0
    for c in text_cols:
        s = df[c].dropna().astype(str)
        ws += int((s != s.str.strip()).sum())
    if ws:
        add("trim_text", ws, f"{ws} text cells have leading or trailing spaces, which can split one category into several.")

    empty = int(df.apply(_blank).all(axis=1).sum())
    if empty:
        add("drop_empty_rows", empty, f"{empty} rows contain no values at all.")

    dup = int(df.duplicated().sum())
    if dup:
        add("drop_duplicates", dup, f"{dup} rows are exact copies of another row and would be counted twice.")

    if t.ts is not None:
        bad = int(t.ts.isna().sum())
        if bad:
            add("drop_invalid_dates", bad, f"{bad} rows have a missing or unreadable date and cannot be placed on a timeline.")

    if t.ts is not None and t.kwh is not None:
        cat = mapping.get("category")
        cumulative = (
            all(looks_cumulative(t.ts[g.index], t.kwh[g.index]) for _, g in df.groupby(df[cat].astype(str)))
            if cat else looks_cumulative(t.ts, t.kwh)
        )
        if cumulative:
            add("cumulative_to_delta", len(df),
                "Consumption values only increase over time, which looks like cumulative meter readings. "
                "Usage per period is the difference between consecutive readings.")

    if t.kwh is not None:
        neg = int((t.kwh < 0).sum())
        if neg:
            add("remove_negative", neg, f"{neg} rows have negative consumption, which is not physically possible for a usage meter.")
        missing = int(t.kwh.isna().sum())
        if missing:
            add("drop_missing_consumption", missing, f"{missing} rows have no readable consumption value.")
            add("interpolate_missing_consumption", missing,
                f"Alternatively, estimate the {missing} missing values from neighbouring readings in time. "
                "Estimated values are marked in the cleaned data.", recommended=False)

    if t.ts is not None:
        keys = [t.ts.dt.floor("s")]
        if mapping.get("category"):
            keys.append(df[mapping["category"]].astype(str).str.strip())
        frame = pd.concat(keys, axis=1)
        frame = frame[t.ts.notna()]
        dup_ts = int(frame.duplicated().sum()) - int(df[t.ts.notna()].duplicated().sum())
        if dup_ts > 0:
            add("dedupe_timestamps", dup_ts,
                f"{dup_ts} rows share a timestamp{' and category' if mapping.get('category') else ''} with another row "
                "but have different values. Only the first is kept.", recommended=False)

    if t.kwh is not None:
        bounds = _iqr_bounds(t.kwh)
        if bounds:
            lo, hi = bounds
            outliers = int(((t.kwh < lo) | (t.kwh > hi)).sum())
            if outliers:
                add("remove_outliers", outliers,
                    f"{outliers} values fall outside {r(lo)} to {r(hi)} (3× the interquartile range). "
                    "They may be meter errors, or real spikes worth investigating, so this is off by default.",
                    recommended=False)

    if t.ts is not None:
        valid = t.ts.dropna()
        if len(valid) > 1 and not valid.is_monotonic_increasing:
            add("sort_by_date", len(df), "Rows are not in date order.")
    return out


def apply(df: pd.DataFrame, mapping: dict[str, Any], actions: list[str]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Run the selected actions in a fixed order. Returns typed data and a per-step log."""
    unknown = [a for a in actions if a not in ACTIONS]
    if unknown:
        raise ValueError(f"Unknown cleaning actions: {', '.join(unknown)}")
    if "drop_missing_consumption" in actions and "interpolate_missing_consumption" in actions:
        raise ValueError("Choose either removing or interpolating missing consumption, not both.")

    ts_col, kwh_col, cost_col, cat_col = (mapping.get(k) for k in ("timestamp", "consumption", "cost", "category"))
    dayfirst = bool(mapping.get("dayfirst", True))
    log: list[dict[str, Any]] = []
    selected = set(actions)

    def step(name: str, fn) -> None:
        before = len(work_ref[0])
        changed, detail = fn()
        log.append({
            "action": name,
            "title": ACTIONS[name]["title"] if name in ACTIONS else name,
            "rows_before": before,
            "rows_after": len(work_ref[0]),
            "values_changed": int(changed),
            "detail": detail,
        })

    work_ref = [df.copy()]  # mutable holder so nested functions can replace the frame

    def trim_text():
        w = work_ref[0]
        changed = 0
        for c in _text_columns(w):
            s = w[c]
            mask = s.notna() & s.map(lambda v: isinstance(v, str))
            stripped = s[mask].str.strip()
            changed += int((stripped != s[mask]).sum())
            w.loc[mask, c] = stripped
        return changed, "Leading and trailing spaces removed."

    def drop_empty_rows():
        w = work_ref[0]
        work_ref[0] = w[~w.apply(_blank).all(axis=1)]
        return 0, "Empty rows removed."

    def drop_duplicates():
        work_ref[0] = work_ref[0].drop_duplicates()
        return 0, "Exact duplicates removed (first occurrence kept)."

    def coerce():
        w = work_ref[0] = work_ref[0].copy()
        w[ts_col] = parse_datetime(w[ts_col], dayfirst)
        w[kwh_col] = parse_numeric(w[kwh_col])
        if cost_col:
            w[cost_col] = parse_numeric(w[cost_col])
        if cat_col:
            w[cat_col] = w[cat_col].map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v))
        return 0, "Dates and numbers parsed (units, currency symbols and thousands separators stripped)."

    def drop_invalid_dates():
        w = work_ref[0]
        work_ref[0] = w[w[ts_col].notna()]
        return 0, "Rows without a valid date removed."

    def cumulative_to_delta():
        w = work_ref[0].sort_values(ts_col)
        if cat_col:
            delta = w.groupby(w[cat_col].fillna("—"), sort=False)[kwh_col].diff()
        else:
            delta = w[kwh_col].diff()
        changed = int(delta.notna().sum())
        w[kwh_col] = delta
        # The first reading of each series has no previous reading to subtract from.
        work_ref[0] = w[w[kwh_col].notna()]
        return changed, "Each reading replaced by the difference from the previous reading; first reading per series dropped."

    def remove_negative():
        w = work_ref[0]
        work_ref[0] = w[~(w[kwh_col] < 0)]
        return 0, "Negative consumption rows removed."

    def drop_missing_consumption():
        w = work_ref[0]
        work_ref[0] = w[w[kwh_col].notna()]
        return 0, "Rows with missing consumption removed."

    def interpolate_missing_consumption():
        w = work_ref[0].sort_values(ts_col)
        missing = w[kwh_col].isna()
        w["is_estimated"] = missing
        valid_ts = w[ts_col].notna()

        def interp(g: pd.DataFrame) -> pd.Series:
            s = g.set_index(ts_col)[kwh_col]
            if s.notna().sum() < 2:
                return pd.Series(s.values, index=g.index)
            filled = s.interpolate(method="time", limit_direction="both")
            return pd.Series(filled.values, index=g.index)

        sub = w[valid_ts]
        if cat_col:
            parts = [interp(g) for _, g in sub.groupby(sub[cat_col].fillna("—"), sort=False)]
            filled = pd.concat(parts) if parts else pd.Series(dtype=float)
        else:
            filled = interp(sub)
        w.loc[filled.index, kwh_col] = filled
        still = int(w[kwh_col].isna().sum())
        changed = int(missing.sum()) - still
        work_ref[0] = w[w[kwh_col].notna()]
        return changed, f"{changed} values estimated from neighbouring readings (column 'is_estimated' marks them)." + (
            f" {still} could not be estimated and were removed." if still else "")

    def dedupe_timestamps():
        w = work_ref[0]
        keys = [ts_col] + ([cat_col] if cat_col else [])
        work_ref[0] = w.drop_duplicates(subset=keys, keep="first")
        return 0, "Repeated timestamps reduced to the first row."

    def remove_outliers():
        w = work_ref[0]
        bounds = _iqr_bounds(w[kwh_col])
        if not bounds:
            return 0, "Not enough spread in the data to define outliers; nothing removed."
        lo, hi = bounds
        work_ref[0] = w[~((w[kwh_col] < lo) | (w[kwh_col] > hi))]
        return 0, f"Values outside {r(lo)} to {r(hi)} removed."

    def sort_by_date():
        work_ref[0] = work_ref[0].sort_values(ts_col, kind="stable")
        return 0, "Rows sorted by date."

    fns = {
        "trim_text": trim_text,
        "drop_empty_rows": drop_empty_rows,
        "drop_duplicates": drop_duplicates,
        "drop_invalid_dates": drop_invalid_dates,
        "cumulative_to_delta": cumulative_to_delta,
        "remove_negative": remove_negative,
        "drop_missing_consumption": drop_missing_consumption,
        "interpolate_missing_consumption": interpolate_missing_consumption,
        "dedupe_timestamps": dedupe_timestamps,
        "remove_outliers": remove_outliers,
        "sort_by_date": sort_by_date,
    }

    for name in ("trim_text", "drop_empty_rows", "drop_duplicates"):
        if name in selected:
            step(name, fns[name])
    # Type coercion always runs: analysis needs real dates and numbers.
    before = len(work_ref[0])
    _, detail = coerce()
    log.append({"action": "parse_types", "title": "Parse dates and numbers", "rows_before": before,
                "rows_after": len(work_ref[0]), "values_changed": 0, "detail": detail})
    for name in PIPELINE_ORDER[3:]:
        if name in selected:
            step(name, fns[name])

    out = work_ref[0].reset_index(drop=True)
    return out, log


def minimal_typed(df: pd.DataFrame, mapping: dict[str, Any]) -> pd.DataFrame:
    """Rows usable for analysis when the user has not run cleaning yet (no rows are invented)."""
    out, _ = apply(df, mapping, ["drop_invalid_dates", "drop_missing_consumption"])
    return out
