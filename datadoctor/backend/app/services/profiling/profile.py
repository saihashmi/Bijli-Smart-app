"""Column and dataset profiles computed from the current snapshot. Pure functions, no I/O.

Every number in a profile is an exact count over all rows (no sampling). Type labels describe
the dominant kind of value in a column; they do not claim to know the business meaning.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from .values import ColumnValues, classify

FAMILY = {
    "native_number": "number",
    "numeric_text": "number",
    "native_date": "date",
    "date_text": "date",
    "native_bool": "boolean",
    "bool_text": "boolean",
    "text": "text",
    "other": "other",
}
CATEGORY_MAX_UNIQUE = 50
TOP_N = 10
HISTOGRAM_BINS = 20


def _r(x: Any, digits: int = 6) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, digits)


def _iso(ts: Any) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    ts = pd.Timestamp(ts)
    return ts.isoformat() if ts != ts.normalize() else ts.date().isoformat()


def _display(v: Any) -> str:
    from ..ingest.workbook import display_value

    return display_value(v)


def _histogram(values: np.ndarray) -> list[dict[str, float | int]]:
    if len(values) == 0:
        return []
    lo, hi = float(values.min()), float(values.max())
    if lo == hi:
        return [{"start": lo, "end": hi, "count": int(len(values))}]
    counts, edges = np.histogram(values, bins=HISTOGRAM_BINS, range=(lo, hi))
    return [{"start": _r(edges[i]), "end": _r(edges[i + 1]), "count": int(c)} for i, c in enumerate(counts)]


def column_profile(name: str, series: pd.Series, today: datetime | None = None) -> dict[str, Any]:
    return _column_profile(name, series, classify(series), today)


def _column_profile(name: str, series: pd.Series, cv: ColumnValues, today: datetime | None) -> dict[str, Any]:
    n = cv.n
    present = ~cv.missing
    non_missing = int(present.sum())
    family_counts: dict[str, int] = {}
    class_counts = cv.classes[present].value_counts().to_dict()
    for cls, cnt in class_counts.items():
        fam = FAMILY.get(cls, "other")
        family_counts[fam] = family_counts.get(fam, 0) + int(cnt)

    prof: dict[str, Any] = {
        "name": name,
        "rows": n,
        "non_missing": non_missing,
        "missing": n - non_missing,
        "missing_pct": _r((n - non_missing) / n * 100, 2) if n else 0.0,
        "missing_kinds": cv.missing_kinds,
        "class_counts": {k: int(v) for k, v in class_counts.items()},
        "whitespace_issues": cv.whitespace_issues,
        "repeated_spaces": cv.repeated_spaces,
    }
    if non_missing == 0:
        prof.update(type="empty", family="empty", consistency=None, mixed=False, unique=0, examples=[])
        return prof

    family = max(family_counts, key=lambda f: (family_counts[f], f == "text"))
    consistency = family_counts[family] / non_missing
    raw_present = series[present]
    # Unique counts and frequencies use the raw cell values (hash-based, fast); only shown values are formatted.
    unique = int(raw_present.nunique(dropna=True))
    prof.update(
        family=family,
        consistency=_r(consistency, 4),
        mixed=consistency < 0.95,
        family_counts=family_counts,
        unique=unique,
        unique_pct=_r(unique / non_missing * 100, 2),
        examples=[{"row": int(i), "value": _display(v)} for i, v in raw_present.head(5).items()],
    )

    if family == "number":
        nums = cv.numbers.dropna().to_numpy(dtype=float)
        is_int = bool(len(nums)) and bool(np.all(np.mod(nums, 1) == 0))
        prof["type"] = "integer" if is_int else "number"
        q = np.quantile(nums, [0.25, 0.5, 0.75]) if len(nums) else [None] * 3
        prof["numeric"] = {
            "count": int(len(nums)),
            "min": _r(nums.min()) if len(nums) else None,
            "max": _r(nums.max()) if len(nums) else None,
            "mean": _r(nums.mean()) if len(nums) else None,
            "median": _r(q[1]),
            "std": _r(nums.std(ddof=1)) if len(nums) > 1 else None,
            "q1": _r(q[0]),
            "q3": _r(q[2]),
            "negatives": int((nums < 0).sum()),
            "zeros": int((nums == 0).sum()),
            "stored_as_text": int(class_counts.get("numeric_text", 0)),
            "histogram": _histogram(nums),
            "excel_serial_candidates": int(((nums >= 25569) & (nums <= 73051) & (np.mod(nums, 1) == 0)).sum())
            if is_int
            else 0,
        }
    elif family == "date":
        prof["type"] = "datetime" if cv.has_time else "date"
        known = cv.dates.dropna()
        now = pd.Timestamp(today or datetime.now(UTC)).tz_localize(None)
        ev = cv.date_evidence or {}
        prof["date"] = {
            "native": int(class_counts.get("native_date", 0)),
            "text": int(class_counts.get("date_text", 0)),
            "formats": cv.date_formats,
            "evidence": ev,
            "ambiguous": int(ev.get("ambiguous", 0)),
            "invalid": int(ev.get("invalid", 0)),
            "resolved": int(len(known)),
            "min": _iso(known.min()) if len(known) else None,
            "max": _iso(known.max()) if len(known) else None,
            "future": int((known > now).sum()),
            "range_note": (
                f"Range excludes {ev.get('ambiguous', 0)} ambiguous and {ev.get('invalid', 0)} invalid values."
                if ev.get("ambiguous", 0) or ev.get("invalid", 0)
                else None
            ),
        }
    elif family == "boolean":
        prof["type"] = "boolean"
        lowered = raw_present.map(lambda v: str(v).strip().lower() if isinstance(v, str) else v)
        trues = int(lowered.isin([True, "true", "yes", "y"]).sum())
        prof["boolean"] = {"true": trues, "false": int(family_counts["boolean"] - trues)}
    elif family == "other":
        prof["type"] = "other"
    else:
        # A small set of repeated labels is a category; mostly-unique text (names, notes, IDs) is free text.
        prof["type"] = "category" if unique <= CATEGORY_MAX_UNIQUE and unique <= 0.8 * non_missing else "text"
        lengths = raw_present.map(lambda v: len(v) if isinstance(v, str) else len(_display(v)))
        prof["text"] = {"min_length": int(lengths.min()), "max_length": int(lengths.max())}

    if prof["type"] in ("category", "text", "boolean") or unique <= CATEGORY_MAX_UNIQUE:
        top = raw_present.value_counts().head(TOP_N)
        prof["top_values"] = [
            {"value": _display(v), "count": int(c), "pct": _r(c / non_missing * 100, 2)} for v, c in top.items()
        ]
        prof["top_values_other"] = int(non_missing - int(top.sum()))
    return prof


def dataset_profile(
    df: pd.DataFrame, today: datetime | None = None, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    rows, cols = df.shape
    classified = {c: classify(df[c]) for c in df.columns}
    columns = [_column_profile(str(c), df[c], classified[c], today) for c in df.columns]
    missing_cells = sum(c["missing"] for c in columns)
    total_cells = rows * cols
    if rows:
        duplicate_rows = int(df.duplicated(keep="first").sum())
        missing_matrix = pd.concat([classified[c].missing for c in df.columns], axis=1) if cols else None
        empty_rows = int(missing_matrix.all(axis=1).sum()) if missing_matrix is not None else 0
    else:
        duplicate_rows = empty_rows = 0
    from .issues import detect

    issues = detect(df, classified, columns, context or {})
    return {
        "issues": issues,
        "rows": rows,
        "columns": cols,
        "total_cells": total_cells,
        "missing_cells": missing_cells,
        "missing_pct": _r(missing_cells / total_cells * 100, 2) if total_cells else 0.0,
        "duplicate_rows": duplicate_rows,
        "empty_rows": empty_rows,
        "empty_columns": sum(1 for c in columns if c["non_missing"] == 0),
        "column_profiles": columns,
    }
