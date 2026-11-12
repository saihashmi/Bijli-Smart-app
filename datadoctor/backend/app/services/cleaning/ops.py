"""The 17 cleaning operations (SPEC §11). Each is a pure function: (data, params) → OpResult.

Rules that every operation follows:
* The input frame is never modified; a new frame is returned.
* Row identity is the DataFrame index (original data-row position), kept through every step.
* Counts are exact. Values that cannot be converted are reported, never silently changed.
* Missing values are never filled with zero unless the user typed 0.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..ingest.workbook import display_value
from ..profiling.values import EXCEL_ERRORS, NULL_TOKENS, classify
from . import params as P

MAX_FAILURES_LISTED = 200


class OpError(ValueError):
    """Invalid request for this data (e.g. unknown column). Shown to the user."""


@dataclass
class OpResult:
    df: pd.DataFrame
    affected_rows: int
    changed: pd.Index  # labels of rows changed / removed / flagged (for previews)
    focus: list[str]  # columns to show in before/after previews
    summary: str
    added_columns: list[str] = field(default_factory=list)
    removed_columns: list[str] = field(default_factory=list)
    removed_rows: int = 0
    renamed: dict[str, str] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    failure_count: int = 0
    warnings: list[str] = field(default_factory=list)
    date_rule: tuple[str, str] | None = None  # (column, interpretation) confirmed by the user


# ---------------- helpers ----------------


def _need(df: pd.DataFrame, *cols: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise OpError(f"Unknown column(s): {', '.join(missing)}")


def _text_columns(df: pd.DataFrame, requested: list[str]) -> list[str]:
    if requested:
        _need(df, *requested)
        return list(requested)
    return [c for c in df.columns if df[c].map(lambda v: isinstance(v, str)).any()]


def _same(a: Any, b: Any) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if type(a) is not type(b):
        return False
    if isinstance(a, float) and np.isnan(a) and np.isnan(b):
        return True
    return a == b


def _changed_mask(before: pd.Series, after: pd.Series) -> np.ndarray:
    return np.fromiter(
        (not _same(a, b) for a, b in zip(before.to_numpy(), after.to_numpy(), strict=True)),
        dtype=bool,
        count=len(before),
    )


def _map_strings(series: pd.Series, fn: Callable[[str], str]) -> pd.Series:
    """Apply fn to string cells only, computing each distinct string once."""
    out = series.copy()
    mask = series.map(lambda v: isinstance(v, str))
    if mask.any():
        uniques = pd.unique(series[mask])
        lookup = {u: fn(u) for u in uniques}
        out[mask] = series[mask].map(lookup)
    return out


def _unique_name(df: pd.DataFrame, base: str) -> str:
    name, i = base, 2
    while name in df.columns:
        name, i = f"{base} ({i})", i + 1
    return name


def _column_edit(df: pd.DataFrame, columns: list[str], fn: Callable[[pd.Series], pd.Series], what: str) -> OpResult:
    out = df.copy()
    changed_any = np.zeros(len(df), dtype=bool)
    cells = 0
    for c in columns:
        new = fn(df[c])
        mask = _changed_mask(df[c], new)
        changed_any |= mask
        cells += int(mask.sum())
        out[c] = new
    rows = int(changed_any.sum())
    return OpResult(
        out, rows, df.index[changed_any], columns, f"{what}: {cells:,} value(s) changed in {rows:,} row(s)."
    )


def _num_or_str(v: float) -> Any:
    return int(v) if float(v).is_integer() and abs(v) < 2**53 else float(v)


# ---------------- 1–2 duplicates ----------------


def remove_exact_duplicates(df: pd.DataFrame, p: P.RemoveExactDuplicates, ctx: dict) -> OpResult:
    dup = df.duplicated(keep=p.keep)
    out = df[~dup]
    n = int(dup.sum())
    return OpResult(
        out,
        n,
        df.index[dup.to_numpy()],
        list(df.columns[:6]),
        f"{n:,} exact duplicate row(s) removed (kept the {p.keep} occurrence).",
        removed_rows=n,
    )


def key_duplicates(df: pd.DataFrame, p: P.KeyDuplicates, ctx: dict) -> OpResult:
    _need(df, *p.key_columns)
    keys = df[p.key_columns].map(lambda v: display_value(v) if v is not None else None)
    dup = keys.duplicated(keep=p.keep).to_numpy()
    n = int(dup.sum())
    groups = int(keys[keys.duplicated(keep=False)].drop_duplicates().shape[0])
    keys_txt = ", ".join(p.key_columns)
    if p.mode == "remove":
        return OpResult(
            df[~dup],
            n,
            df.index[dup],
            p.key_columns + [c for c in df.columns if c not in p.key_columns][:3],
            f"{n:,} row(s) repeating a key ({keys_txt}) removed; {groups:,} key value(s) were repeated.",
            removed_rows=n,
        )
    out = df.copy()
    flag = _unique_name(out, "is_duplicate_key")
    out[flag] = dup.tolist()
    return OpResult(
        out,
        n,
        df.index[dup],
        p.key_columns + [flag],
        f"{n:,} row(s) repeat a key ({keys_txt}); flagged in the new column “{flag}”. Nothing was removed.",
        added_columns=[flag],
    )


# ---------------- 3–6 text ----------------

_WS = re.compile(r"\s+")


def trim_whitespace(df: pd.DataFrame, p: P.TextColumns, ctx: dict) -> OpResult:
    cols = _text_columns(df, p.columns)
    return _column_edit(
        df, cols, lambda s: _map_strings(s, lambda v: v.strip(" \t\r\n   ")), "Leading and trailing spaces removed"
    )


def normalize_spaces(df: pd.DataFrame, p: P.TextColumns, ctx: dict) -> OpResult:
    cols = _text_columns(df, p.columns)
    return _column_edit(df, cols, lambda s: _map_strings(s, lambda v: _WS.sub(" ", v)), "Repeated spaces collapsed")


def _sentence(v: str) -> str:
    v = v.lower()
    i = next((k for k, ch in enumerate(v) if ch.isalpha()), None)
    return v if i is None else v[:i] + v[i].upper() + v[i + 1 :]


def standardize_case(df: pd.DataFrame, p: P.StandardizeCase, ctx: dict) -> OpResult:
    cols = _text_columns(df, p.columns)
    fn = {"upper": str.upper, "lower": str.lower, "title": str.title, "sentence": _sentence}[p.style]
    return _column_edit(df, cols, lambda s: _map_strings(s, fn), f"Capitalisation set to {p.style} case")


def normalize_categories(df: pd.DataFrame, p: P.NormalizeCategories, ctx: dict) -> OpResult:
    _need(df, p.column)
    mapping = {k: v for k, v in p.mapping.items() if k != v}
    present = set(df[p.column].map(lambda v: v if isinstance(v, str) else None).dropna())
    unknown = [k for k in mapping if k not in present]
    res = _column_edit(
        df,
        [p.column],
        lambda s: _map_strings(s, lambda v: mapping.get(v, v)),
        f"{len(mapping)} label variant(s) replaced in “{p.column}”",
    )
    if unknown:
        res.warnings.append(f"{len(unknown)} label(s) in the mapping do not occur in this column and were ignored.")
    return res


def category_suggestions(series: pd.Series) -> list[dict[str, Any]]:
    """Groups of labels equal after trimming, collapsing spaces and case-folding; most frequent spelling first."""
    strs = series[series.map(lambda v: isinstance(v, str))]
    counts = strs.value_counts()
    groups: dict[str, list[tuple[str, int]]] = {}
    for label, c in counts.items():
        key = _WS.sub(" ", str(label)).strip().casefold()
        if key:
            groups.setdefault(key, []).append((str(label), int(c)))
    out = []
    for members in groups.values():
        if len(members) > 1:
            members.sort(key=lambda m: (-m[1], m[0] != m[0].strip(), not m[0].strip().istitle(), m[0]))
            target = _WS.sub(" ", members[0][0]).strip()
            out.append({"suggested": target, "variants": [{"label": lb, "count": c} for lb, c in members]})
    out.sort(key=lambda g: -sum(v["count"] for v in g["variants"]))
    return out


# ---------------- 7 numbers ----------------

_CURRENCY = re.compile(r"(?i)rs\.?|pkr|inr|usd|aed|sar|[$€£₨]")
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?")


def parse_number(
    text: str, decimal: str = ".", percent: str = "keep_number", parentheses_negative: bool = True
) -> float | None:
    t = text.strip().lower()
    if not t:
        return None
    neg = False
    if re.fullmatch(r"\(.*\)\s*%?", t):
        neg, t = parentheses_negative, t.replace("(", "").replace(")", "")
    t = _CURRENCY.sub("", t).strip()
    if t.endswith("-") and not t.startswith("-"):
        neg, t = True, t[:-1]
    pct = "%" in t
    t = t.replace("%", "").replace(" ", "").replace(" ", "")
    if decimal == ",":
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", "")
    if not _NUMBER.fullmatch(t):
        return None
    val = float(t)
    if pct and percent == "divide_by_100":
        val /= 100
    return -abs(val) if neg else val


def convert_numeric(df: pd.DataFrame, p: P.ConvertNumeric, ctx: dict) -> OpResult:
    _need(df, *p.columns)
    out = df.copy()
    changed_any = np.zeros(len(df), dtype=bool)
    failures: list[dict[str, Any]] = []
    fail_total, converted, added = 0, 0, []
    for c in p.columns:
        cv = classify(df[c])
        missing = cv.missing.to_numpy()
        cache: dict[str, float | None] = {}
        new_vals = []
        failed = np.zeros(len(df), dtype=bool)
        for i, v in enumerate(df[c].to_numpy()):
            if missing[i]:
                new_vals.append(None)
            elif isinstance(v, bool):
                new_vals.append(None)
                failed[i] = True
            elif isinstance(v, (int, float, np.integer, np.floating)):
                new_vals.append(_num_or_str(float(v)))
            elif isinstance(v, str):
                if v not in cache:
                    cache[v] = parse_number(v, p.decimal, p.percent, p.parentheses_negative)
                num = cache[v]
                if num is None:
                    new_vals.append(None)
                    failed[i] = True
                else:
                    new_vals.append(_num_or_str(num))
            else:
                new_vals.append(None)
                failed[i] = True
        new = pd.Series(new_vals, index=df.index, dtype=object)
        mask = _changed_mask(df[c], new)
        # Missing placeholders (N/A, spaces) becoming real empty cells are changes too, but not conversions.
        converted += int((mask & ~missing & ~failed).sum())
        changed_any |= mask
        fail_total += int(failed.sum())
        for i in np.flatnonzero(failed)[: MAX_FAILURES_LISTED - len(failures)]:
            failures.append(
                {"row": int(df.index[i]), "column": c, "value": display_value(df[c].iloc[i]), "reason": "Not a number"}
            )
        if p.on_failure == "keep_raw_column" and failed.any():
            raw_name = _unique_name(out, f"{c}__raw")
            out[raw_name] = df[c]
            added.append(raw_name)
        out[c] = new
    rows = int(changed_any.sum())
    summary = f"{converted:,} value(s) converted to numbers in {rows:,} row(s)."
    if fail_total:
        summary += f" {fail_total:,} value(s) could not be read as numbers and are now empty" + (
            "; the original values are kept in the “__raw” column." if added else " (listed in the failure report)."
        )
    return OpResult(
        out,
        rows,
        df.index[changed_any],
        list(p.columns) + added,
        summary,
        added_columns=added,
        failures=failures,
        failure_count=fail_total,
    )


# ---------------- 8–9 dates ----------------

_ISO = re.compile(r"\d{4}-\d{1,2}-\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?")
_YMD = re.compile(r"(\d{4})[/.](\d{1,2})[/.](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?")
_NUMERIC_DATE = re.compile(
    r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?\s*([ap]m)?)?", re.I
)
_EXCEL_1900 = dt.datetime(1899, 12, 30)
_EXCEL_1904 = dt.datetime(1904, 1, 1)


def _year(y: str) -> int:
    v = int(y)
    return v if len(y) == 4 else (2000 + v if v < 70 else 1900 + v)


def _mk(
    y: int, m: int, d: int, hh: str | None = None, mm: str | None = None, ss: str | None = None, ampm: str | None = None
) -> dt.datetime | None:
    try:
        h = int(hh or 0)
        if ampm:
            h = h % 12 + (12 if ampm.lower() == "pm" else 0)
        return dt.datetime(y, m, d, h, int(mm or 0), int(ss or 0))
    except ValueError:
        return None


def parse_date(value: Any, interpretation: str) -> tuple[dt.datetime | None, str | None]:
    """→ (datetime, None) or (None, reason). Uses ONLY the confirmed interpretation for day/month order."""
    if isinstance(value, dt.datetime):
        return value, None
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day), None
    serial = interpretation.startswith("excel_serial")
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        if not serial:
            return None, "A number, not a date (choose an Excel serial reading for date numbers)"
        base = _EXCEL_1904 if interpretation.endswith("1904") else _EXCEL_1900
        if not (0 < float(value) < 2_958_466):
            return None, "Outside the Excel date range"
        return base + dt.timedelta(days=float(value)), None
    if not isinstance(value, str):
        return None, "Not recognised as a date"
    t = value.strip()
    if serial and re.fullmatch(r"\d+(?:\.\d+)?", t):
        return parse_date(float(t), interpretation)
    if _ISO.fullmatch(t):
        parsed = pd.to_datetime(t, errors="coerce", format="ISO8601")
        return (None, "Not a valid date") if pd.isna(parsed) else (parsed.to_pydatetime(), None)
    m = _YMD.fullmatch(t)
    if m:
        out = _mk(int(m[1]), int(m[2]), int(m[3]), m[4], m[5], m[6])
        return (out, None) if out else (None, "Not a valid date")
    m = _NUMERIC_DATE.fullmatch(t)
    if m:
        a, b, y = int(m[1]), int(m[2]), _year(m[3])
        as_dmy, as_mdy = _mk(y, b, a, m[4], m[5], m[6], m[7]), _mk(y, a, b, m[4], m[5], m[6], m[7])
        if interpretation == "DMY":
            if as_dmy:
                return as_dmy, None
            return None, "Only valid as MM/DD, which contradicts the chosen DD/MM" if as_mdy else "Not a valid date"
        if interpretation == "MDY":
            if as_mdy:
                return as_mdy, None
            return None, "Only valid as DD/MM, which contradicts the chosen MM/DD" if as_dmy else "Not a valid date"
        if as_dmy and as_mdy and as_dmy != as_mdy:
            return None, "Ambiguous: choose DD/MM or MM/DD for this column"
        unique = as_dmy or as_mdy
        return (unique, None) if unique else (None, "Not a valid date")
    if re.search(r"(?i)[a-z]{3}", t) and re.search(r"\d", t):
        if re.fullmatch(r"(?i)[a-z]{3,9}[ \-]\d{2}", t):  # e.g. Mar-25: month-year or month-day? ambiguous
            return None, "Ambiguous month-year text"
        parsed = pd.to_datetime(t, errors="coerce", format="mixed", dayfirst=False)
        if not pd.isna(parsed):
            return parsed.to_pydatetime(), None
    return None, "Not recognised as a date"


def normalize_dates(df: pd.DataFrame, p: P.NormalizeDates, ctx: dict) -> OpResult:
    _need(df, p.column)
    cv = classify(df[p.column])
    missing = cv.missing.to_numpy()
    cache: dict[Any, tuple[Any, str | None]] = {}
    new_vals: list[Any] = []
    failures: list[dict[str, Any]] = []
    failed = np.zeros(len(df), dtype=bool)
    for i, v in enumerate(df[p.column].to_numpy()):
        if missing[i]:
            new_vals.append(None)
            continue
        key = (type(v), v) if not isinstance(v, (dt.date, dt.datetime)) else None
        if key is not None and key in cache:
            parsed, reason = cache[key]
        else:
            parsed, reason = parse_date(v, p.interpretation)
            if key is not None:
                cache[key] = (parsed, reason)
        if parsed is None:
            failed[i] = True
            new_vals.append(None)
            if len(failures) < MAX_FAILURES_LISTED:
                failures.append(
                    {"row": int(df.index[i]), "column": p.column, "value": display_value(v), "reason": reason}
                )
        else:
            new_vals.append(parsed.date() if p.output == "date" else parsed)
    out = df.copy()
    added = []
    if p.on_failure == "keep_raw_column" and failed.any():
        raw = _unique_name(out, f"{p.column}__raw")
        out[raw] = df[p.column]
        added.append(raw)
    new = pd.Series(new_vals, index=df.index, dtype=object)
    mask = _changed_mask(df[p.column], new)
    out[p.column] = new
    n_fail = int(failed.sum())
    label = {
        "DMY": "DD/MM/YYYY",
        "MDY": "MM/DD/YYYY",
        "YMD": "YYYY/MM/DD",
        "excel_serial_1900": "Excel serial (1900)",
        "excel_serial_1904": "Excel serial (1904)",
    }[p.interpretation]
    converted = int((mask & ~failed).sum())
    summary = f"Dates in “{p.column}” read as {label} and stored as real {p.output}s: {converted:,} changed."
    if n_fail:
        summary += f" {n_fail:,} value(s) could not be read and are now empty (see the failure report)."
    return OpResult(
        out,
        int(mask.sum()),
        df.index[mask],
        [p.column] + added,
        summary,
        added_columns=added,
        failures=failures,
        failure_count=n_fail,
        date_rule=(p.column, p.interpretation) if p.interpretation in ("DMY", "MDY") else None,
    )


def identify_invalid_dates(df: pd.DataFrame, p: P.IdentifyInvalidDates, ctx: dict) -> OpResult:
    _need(df, p.column)
    cv = classify(df[p.column])
    present = ~cv.missing.to_numpy()
    classes = cv.classes.to_numpy()
    ok = np.zeros(len(df), dtype=bool)
    for i, v in enumerate(df[p.column].to_numpy()):
        if not present[i]:
            continue
        if classes[i] == "native_date":
            ok[i] = True
            continue
        a, _ = parse_date(v, "DMY")
        b, _ = parse_date(v, "MDY")
        ok[i] = a is not None or b is not None
    invalid = present & ~ok
    out = df.copy()
    flag = _unique_name(out, f"{p.column}__invalid_date")
    out[flag] = invalid.tolist()
    n = int(invalid.sum())
    return OpResult(
        out,
        n,
        df.index[invalid],
        [p.column, flag],
        f"{n:,} value(s) in “{p.column}” are not valid dates under any reading; marked in “{flag}”. "
        "Values were not changed.",
        added_columns=[flag],
    )


# ---------------- 10–12 missing values / empty rows ----------------


def detect_missing(df: pd.DataFrame, p: P.DetectMissing, ctx: dict) -> OpResult:
    cols = _text_columns(df, p.columns)
    tokens = NULL_TOKENS | EXCEL_ERRORS | {t.strip().lower() for t in p.extra_null_tokens if t.strip()}

    def fn(s: pd.Series) -> pd.Series:
        return s.map(lambda v: None if isinstance(v, str) and (not v.strip() or v.strip().lower() in tokens) else v)

    return _column_edit(df, cols, fn, "Blank text and placeholders such as N/A turned into real empty cells")


def handle_missing(df: pd.DataFrame, p: P.HandleMissing, ctx: dict) -> OpResult:
    _need(df, p.column)
    cv = classify(df[p.column])
    missing = cv.missing.to_numpy()
    n = int(missing.sum())
    focus = [p.column]
    if p.strategy == "leave":
        return OpResult(df, 0, df.index[:0], focus, "Missing values left unchanged.")
    if p.strategy == "drop_rows":
        return OpResult(
            df[~missing],
            n,
            df.index[missing],
            focus + [c for c in df.columns if c != p.column][:3],
            f"{n:,} row(s) with a missing “{p.column}” removed.",
            removed_rows=n,
        )
    is_number = cv.numbers.notna().sum() >= 0.5 * max(1, (~cv.missing).sum())
    if p.strategy == "fixed":
        if p.value is None or p.value == "":
            raise OpError("Enter the value to fill missing cells with.")
        num = parse_number(p.value) if is_number else None
        fill: Any = _num_or_str(num) if num is not None else p.value
        how = f"the value “{p.value}”"
    elif p.strategy in ("median", "mean"):
        if not is_number:
            raise OpError("Median and mean can only fill number columns.")
        nums = cv.numbers.dropna()
        if nums.empty:
            raise OpError("There are no numbers in this column to calculate from.")
        val = float(nums.median() if p.strategy == "median" else nums.mean())
        fill = _num_or_str(round(val, 10))
        how = f"the {p.strategy} ({display_value(fill)})"
    else:  # mode
        if is_number:
            raise OpError("Mode filling is for category or text columns; use median or mean for numbers.")
        present = df[p.column][~missing]
        if present.empty:
            raise OpError("There are no values in this column to calculate from.")
        counts = present.map(display_value).value_counts()
        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        fill = next(v for v in present if display_value(v) == top)
        how = f"the most common value (“{display_value(fill)}”)"
    out = df.copy()
    col = out[p.column].copy()
    col[missing] = [fill] * n
    out[p.column] = col
    return OpResult(out, n, df.index[missing], focus, f"{n:,} missing value(s) in “{p.column}” filled with {how}.")


def remove_empty_rows(df: pd.DataFrame, p: P.Empty, ctx: dict) -> OpResult:
    if df.shape[1] == 0:
        return OpResult(df, 0, df.index[:0], [], "No columns.")
    empty = np.column_stack([classify(df[c]).missing.to_numpy() for c in df.columns]).all(axis=1)
    n = int(empty.sum())
    return OpResult(
        df[~empty], n, df.index[empty], list(df.columns[:6]), f"{n:,} completely empty row(s) removed.", removed_rows=n
    )


# ---------------- 13–15 columns ----------------


def rename_columns(df: pd.DataFrame, p: P.RenameColumns, ctx: dict) -> OpResult:
    _need(df, *p.mapping)
    mapping = {k: re.sub(r"\s+", " ", v).strip()[:200] for k, v in p.mapping.items()}
    if any(not v for v in mapping.values()):
        raise OpError("Column names cannot be empty.")
    mapping = {k: v for k, v in mapping.items() if k != v}
    new_names = [mapping.get(c, c) for c in df.columns]
    if len({n.casefold() for n in new_names}) != len(new_names):
        raise OpError("Column names must be unique.")
    out = df.rename(columns=mapping)
    rows = len(df) if mapping else 0
    return OpResult(
        out,
        rows,
        df.index[:0],
        list(mapping.values()),
        f"{len(mapping)} column(s) renamed: " + ", ".join(f"“{k}” → “{v}”" for k, v in mapping.items()),
        renamed=mapping,
    )


def reorder_columns(df: pd.DataFrame, p: P.ReorderColumns, ctx: dict) -> OpResult:
    if sorted(p.order) != sorted(map(str, df.columns)):
        raise OpError("The new order must list every column exactly once.")
    moved = sum(1 for a, b in zip(p.order, df.columns, strict=True) if a != b)
    return OpResult(
        df[p.order],
        len(df) if moved else 0,
        df.index[:0],
        list(p.order[:6]),
        f"Columns reordered ({moved} position(s) changed).",
    )


def remove_columns(df: pd.DataFrame, p: P.RemoveColumns, ctx: dict) -> OpResult:
    _need(df, *p.columns)
    if len(set(p.columns)) >= df.shape[1]:
        raise OpError("At least one column must remain.")
    out = df.drop(columns=p.columns)
    return OpResult(
        out,
        len(df),
        df.index[:0],
        list(p.columns),
        f"{len(p.columns)} column(s) removed: " + ", ".join(f"“{c}”" for c in p.columns) + ".",
        removed_columns=list(p.columns),
    )


# ---------------- 16–17 flags ----------------


def flag_outliers(df: pd.DataFrame, p: P.FlagOutliers, ctx: dict) -> OpResult:
    _need(df, p.column)
    nums = classify(df[p.column]).numbers.to_numpy()
    valid = ~np.isnan(nums)
    if valid.sum() < 3:
        raise OpError("This column needs at least three numbers to look for outliers.")
    if p.method == "iqr":
        k = p.threshold or 3.0
        q1, q3 = np.quantile(nums[valid], [0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - k * iqr, q3 + k * iqr
        rule = f"outside {lo:,.2f} to {hi:,.2f} ({k}× the interquartile range)"
    else:
        k = p.threshold or 3.5
        med = float(np.median(nums[valid]))
        mad = float(np.median(np.abs(nums[valid] - med)))
        if mad == 0:
            raise OpError("Most values are identical, so a robust z-score cannot be calculated. Try the IQR method.")
        lo, hi = med - k * mad / 0.6745, med + k * mad / 0.6745
        rule = f"with a robust z-score above {k} (outside {lo:,.2f} to {hi:,.2f})"
    out_mask = valid & ((nums < lo) | (nums > hi))
    out = df.copy()
    flag = _unique_name(out, f"{p.column}__outlier")
    out[flag] = out_mask.tolist()
    n = int(out_mask.sum())
    return OpResult(
        out,
        n,
        df.index[out_mask],
        [p.column, flag],
        f"{n:,} value(s) in “{p.column}” are {rule}; marked in “{flag}”. Nothing was removed.",
        added_columns=[flag],
    )


_TYPE_LABEL = {
    "native_number": "Number",
    "numeric_text": "Number (as text)",
    "native_date": "Date",
    "date_text": "Date (as text)",
    "native_bool": "Yes/No",
    "bool_text": "Yes/No (as text)",
    "text": "Text",
    "other": "Other",
    "": "Empty",
}


def flag_types(df: pd.DataFrame, p: P.FlagTypes, ctx: dict) -> OpResult:
    _need(df, p.column)
    classes = classify(df[p.column]).classes.map(_TYPE_LABEL)
    out = df.copy()
    flag = _unique_name(out, f"{p.column}__type")
    out[flag] = classes.tolist()
    dominant = classes[classes != "Empty"].str.replace(" (as text)", "", regex=False).value_counts()
    n = int((classes != "Empty").sum() - (dominant.iloc[0] if len(dominant) else 0))
    return OpResult(
        out,
        n,
        df.index[
            (classes != "Empty")
            & (classes.str.replace(" (as text)", "", regex=False) != (dominant.index[0] if len(dominant) else ""))
        ],
        [p.column, flag],
        f"Each value's kind written to “{flag}”; {n:,} value(s) differ from the column's main kind.",
        added_columns=[flag],
    )
