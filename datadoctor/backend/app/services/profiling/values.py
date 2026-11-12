"""Classify raw cell values without changing them. All checks are exact and vectorised per column.

Classes for a non-missing value:
  native_number · numeric_text · native_date · date_text · native_bool · bool_text · text · other
Missing values: empty cell, whitespace-only text, a null token (N/A, null, -, …) or an Excel error (#DIV/0! …).

Date text is NEVER interpreted here when it is ambiguous: 03/04/2026 is counted as ambiguous, with
evidence counts for DD/MM and MM/DD, so that the user decides (SPEC §11 date rules).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

NULL_TOKENS = {"na", "n/a", "n.a.", "null", "none", "nil", "nan", "-", "--", "—", "?", "missing", "#n/a"}
EXCEL_ERRORS = {"#div/0!", "#ref!", "#value!", "#name?", "#num!", "#null!", "#getting_data", "#spill!", "#calc!"}

_CUR = r"(?:rs\.?|pkr|inr|usd|aed|sar|\$|€|£|₨)"
NUMERIC_RE = (
    rf"(?i)^\s*{_CUR}?\s*[-+]?\s*{_CUR}?\s*\(?\s*{_CUR}?\s*"
    r"(?:\d{1,3}(?:,\d{2,3})+|\d+)?(?:\.\d+)?(?:e[-+]?\d+)?"
    rf"\s*\)?\s*%?\s*-?\s*{_CUR}?\s*$"
)
_HAS_DIGIT = r"\d"
BOOL_TRUE = {"true", "yes", "y"}
BOOL_FALSE = {"false", "no", "n"}

MONTHS = (
    "january|february|march|april|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec"
)
_TIME = r"(?:[ T]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:\s?[ap]m)?)?"
DATE_PATTERNS: dict[str, str] = {
    # key: human-readable format family
    "YYYY-MM-DD": rf"^\d{{4}}-\d{{1,2}}-\d{{1,2}}{_TIME}$",
    "YYYY/MM/DD": rf"^\d{{4}}[/.]\d{{1,2}}[/.]\d{{1,2}}{_TIME}$",
    "NN/NN/YYYY": rf"^\d{{1,2}}/\d{{1,2}}/\d{{4}}{_TIME}$",
    "NN-NN-YYYY": rf"^\d{{1,2}}-\d{{1,2}}-\d{{4}}{_TIME}$",
    "NN.NN.YYYY": rf"^\d{{1,2}}\.\d{{1,2}}\.\d{{4}}{_TIME}$",
    "NN/NN/YY": rf"^\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2}}{_TIME}$",
    "DD Mon YYYY": rf"(?i)^\d{{1,2}}[ \-](?:{MONTHS})\.?[\s,\-]*\d{{2,4}}{_TIME}$",
    "Mon DD, YYYY": rf"(?i)^(?:{MONTHS})\.?[ \-]\d{{1,2}}(?:st|nd|rd|th)?,?[ \-]\d{{4}}{_TIME}$",
    "Mon YYYY": rf"(?i)^(?:{MONTHS})\.?[ \-]\d{{4}}$",
}
_SLASH_PARTS = r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})"


@dataclass
class ColumnValues:
    """Per-value classification of one column (index-aligned boolean masks) plus parsed helpers."""

    n: int
    missing: pd.Series
    missing_kinds: dict[str, int]
    classes: pd.Series  # category label per row ('' for missing)
    numbers: pd.Series  # float value for native_number/numeric_text, NaN otherwise
    dates: pd.Series  # Timestamp for unambiguous dates (native or text), NaT otherwise
    date_formats: dict[str, int] = field(default_factory=dict)
    date_evidence: dict[str, int] = field(default_factory=dict)
    date_ambiguous_by_format: dict[str, int] = field(default_factory=dict)
    plain_numeric_text: int = 0  # numeric text with no formatting at all, e.g. "1250.5" (normal in CSV files)
    edge_ws: pd.Series | None = None  # per-row: text with leading/trailing whitespace
    repeated_ws: pd.Series | None = None  # per-row: text with repeated inner spaces
    str_codes: np.ndarray | None = None  # factorize codes for string rows (aligned with str_index)
    str_index: np.ndarray | None = None
    str_uniques: np.ndarray | None = None
    whitespace_issues: int = 0  # text with leading/trailing whitespace
    repeated_spaces: int = 0
    has_time: bool = False


def _year(y: pd.Series) -> pd.Series:
    y = y.astype(int)
    # Two-digit years follow Excel's rule: 00–29 → 2000s is Excel's; SPEC fixes 00–69 → 2000s, 70–99 → 1900s.
    return y.where(y >= 100, np.where(y < 70, 2000 + y, 1900 + y))


def _valid_dates(year: pd.Series, month: pd.Series, day: pd.Series) -> pd.Series:
    out = pd.to_datetime(pd.DataFrame({"year": year, "month": month, "day": day}), errors="coerce")
    return out


def parse_numeric_text(s: pd.Series) -> pd.Series:
    """Parse already-validated numeric text: strip currency, thousands separators, %, handle (x) and trailing -."""
    t = s.str.strip().str.lower()
    neg = t.str.contains(r"^\s*\(.*\)\s*%?\s*$|^[^\d]*-|-\s*$", regex=True)
    cleaned = t.str.replace(rf"{_CUR}|[,%()\s+-]", "", regex=True)
    vals = pd.to_numeric(cleaned, errors="coerce")
    return vals.where(~neg, -vals.abs())


_CLASS_CODES = [
    "",
    "native_number",
    "numeric_text",
    "native_date",
    "date_text",
    "native_bool",
    "bool_text",
    "text",
    "other",
]
_NUMERIC_C = re.compile(NUMERIC_RE)
_DATE_C = re.compile(
    "|".join(f"(?P<f{i}>{pat.removeprefix('(?i)')})" for i, pat in enumerate(DATE_PATTERNS.values())), re.I
)
_DATE_KEYS = list(DATE_PATTERNS.keys())
_REPEATED_SPACE = re.compile(r"\S\s{2,}\S")
_PLAIN_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_NATIVE_NUMBER_TYPES = (int, float, np.integer, np.floating)


def _classify_string(v: str) -> tuple[int, str | None, str, bool, bool]:
    """→ (missing-kind code, class, date format key, has edge whitespace, has repeated inner spaces).
    missing-kind: 0 = present, 2 = whitespace-only, 3 = null token, 4 = Excel error."""
    st = v.strip()
    if not st:
        return 2, None, "", False, False
    low = st.lower()
    if low in NULL_TOKENS:
        return 3, None, "", False, False
    if low in EXCEL_ERRORS:
        return 4, None, "", False, False
    edge = st != v
    rep = bool(_REPEATED_SPACE.search(v))
    if low in BOOL_TRUE or low in BOOL_FALSE:
        return 0, "bool_text", "", edge, rep
    if any(ch.isdigit() for ch in st) and _NUMERIC_C.fullmatch(st):
        return 0, "numeric_text", "", edge, rep
    m = _DATE_C.fullmatch(st)
    if m:
        return 0, "date_text", _DATE_KEYS[int(m.lastgroup[1:])], edge, rep
    return 0, "text", "", edge, rep


def classify(series: pd.Series) -> ColumnValues:
    """Exact per-row classification. Each DISTINCT string is analysed once and the result is copied to all
    rows holding it (spreadsheet columns repeat heavily), which keeps profiling fast on large sheets."""
    values = series.to_numpy(dtype=object)
    n = len(values)
    index = series.index
    is_str = np.fromiter((type(v) is str for v in values), dtype=bool, count=n)
    is_none = pd.isna(series).to_numpy() & ~is_str

    missing_kind = np.zeros(n, dtype=np.int8)  # 0 present, 1 empty, 2 ws-only, 3 token, 4 excel error
    missing_kind[is_none] = 1
    classes = np.array([""] * n, dtype=object)
    numbers = np.full(n, np.nan)
    dates = pd.Series(pd.NaT, index=index, dtype="datetime64[ns]")
    date_formats: dict[str, int] = {}
    evidence = {"iso_or_named": 0, "dmy_only": 0, "mdy_only": 0, "ambiguous": 0, "same_either_way": 0, "invalid": 0}
    whitespace_issues = repeated = plain_numeric = 0
    edge_mask = np.zeros(n, dtype=bool)
    rep_mask = np.zeros(n, dtype=bool)
    codes = uniques = None
    ambiguous_by_format: dict[str, int] = {}

    # ---- non-string values (native cells from Excel) ----
    other_idx = np.flatnonzero(~is_str & ~is_none)
    if len(other_idx):
        for i in other_idx:
            v = values[i]
            if isinstance(v, bool):
                classes[i] = "native_bool"
            elif isinstance(v, _NATIVE_NUMBER_TYPES):
                classes[i] = "native_number"
                numbers[i] = float(v)
            elif isinstance(v, (dt.datetime, dt.date)):
                classes[i] = "native_date"
            else:
                classes[i] = "other"
        nd = classes == "native_date"
        if nd.any():
            dates.iloc[np.flatnonzero(nd)] = pd.to_datetime(pd.Series(values[nd]), errors="coerce").to_numpy()

    # ---- strings: classify distinct values once ----
    str_idx = np.flatnonzero(is_str)
    if len(str_idx):
        codes, uniques = pd.factorize(pd.Series(values[str_idx], dtype=object), sort=False)
        info = [_classify_string(u) for u in uniques]
        u_missing = np.array([x[0] for x in info], dtype=np.int8)
        u_class = np.array([x[1] or "" for x in info], dtype=object)
        u_fmt = np.array([x[2] for x in info], dtype=object)
        u_edge = np.array([x[3] for x in info], dtype=bool)
        u_rep = np.array([x[4] for x in info], dtype=bool)
        counts = np.bincount(codes, minlength=len(uniques))
        missing_kind[str_idx] = u_missing[codes]
        classes[str_idx] = u_class[codes]
        whitespace_issues = int(counts[u_edge].sum())
        repeated = int(counts[u_rep].sum())
        edge_mask[str_idx] = u_edge[codes]
        rep_mask[str_idx] = u_rep[codes]
        uniques = np.asarray(uniques, dtype=object)

        num_u = np.flatnonzero(u_class == "numeric_text")
        if len(num_u):
            parsed = parse_numeric_text(pd.Series(uniques[num_u], dtype=object)).to_numpy(dtype=float)
            u_num = np.full(len(uniques), np.nan)
            u_num[num_u] = parsed
            mask = u_class[codes] == "numeric_text"
            numbers[str_idx[mask]] = u_num[codes[mask]]
            u_plain = np.array([bool(_PLAIN_NUMBER.fullmatch(str(uniques[i]))) for i in num_u], dtype=bool)
            plain_numeric = int(counts[num_u[u_plain]].sum())

        date_u = np.flatnonzero(u_class == "date_text")
        if len(date_u):
            for key in _DATE_KEYS:
                c = int(counts[date_u][u_fmt[date_u] == key].sum())
                if c:
                    date_formats[key] = c
            u_dates = pd.Series(pd.NaT, index=range(len(uniques)), dtype="datetime64[ns]")
            u_ev = {k: np.zeros(len(uniques), dtype=bool) for k in evidence}
            _resolve_date_text(pd.Series(uniques[date_u], index=date_u, dtype=object).str.strip(), u_dates, u_ev)
            for k in evidence:
                evidence[k] = int(counts[u_ev[k]].sum())
            for key in date_formats:
                c = int(counts[u_ev["ambiguous"] & (u_fmt == key)].sum())
                if c:
                    ambiguous_by_format[key] = c
            mask = u_class[codes] == "date_text"
            dates.iloc[str_idx[mask]] = u_dates.to_numpy()[codes[mask]]

    missing = pd.Series(missing_kind > 0, index=index)
    has_time = False
    known = dates.dropna()
    if len(known):
        has_time = bool((known.dt.normalize() != known).any())
    return ColumnValues(
        n=n,
        missing=missing,
        missing_kinds={
            "empty": int((missing_kind == 1).sum()),
            "whitespace_only": int((missing_kind == 2).sum()),
            "null_token": int((missing_kind == 3).sum()),
            "excel_error": int((missing_kind == 4).sum()),
        },
        classes=pd.Series(classes, index=index, dtype=object),
        numbers=pd.Series(numbers, index=index),
        dates=dates,
        date_formats=date_formats,
        date_evidence=evidence if date_formats else {},
        date_ambiguous_by_format=ambiguous_by_format,
        plain_numeric_text=plain_numeric,
        whitespace_issues=whitespace_issues,
        repeated_spaces=repeated,
        edge_ws=pd.Series(edge_mask, index=index),
        repeated_ws=pd.Series(rep_mask, index=index),
        str_codes=codes,
        str_index=str_idx,
        str_uniques=uniques,
        has_time=has_time,
    )


def _resolve_date_text(values: pd.Series, dates: pd.Series, evidence: dict[str, np.ndarray]) -> None:
    """For each distinct date string (index = position in the uniques array): fill `dates` only when the
    meaning is certain, and mark which evidence bucket it belongs to."""
    parts = values.str.extract(_SLASH_PARTS)
    slashy = parts[0].notna() & ~values.str.match(r"^\d{4}")
    named = values[~slashy]
    if len(named):
        parsed = pd.to_datetime(named, errors="coerce", format="mixed", dayfirst=False)
        ok = parsed.notna()
        dates.loc[parsed.index[ok]] = parsed[ok].to_numpy()
        evidence["iso_or_named"][parsed.index[ok]] = True
        evidence["invalid"][parsed.index[~ok]] = True
    if slashy.any():
        p = parts[slashy]
        a, b, y = p[0].astype(int), p[1].astype(int), _year(p[2])
        as_dmy = _valid_dates(y, b, a)  # a = day, b = month
        as_mdy = _valid_dates(y, a, b)  # a = month, b = day
        dmy_ok, mdy_ok = as_dmy.notna(), as_mdy.notna()
        same = dmy_ok & mdy_ok & (a == b)
        buckets = {
            "dmy_only": dmy_ok & ~mdy_ok,
            "mdy_only": mdy_ok & ~dmy_ok,
            "ambiguous": dmy_ok & mdy_ok & ~same,
            "same_either_way": same,
            "invalid": ~dmy_ok & ~mdy_ok,
        }
        for key, mask in buckets.items():
            evidence[key][mask[mask].index] = True
        known = buckets["dmy_only"] | same
        dates.loc[known[known].index] = as_dmy[known].to_numpy()
        mdy = buckets["mdy_only"]
        dates.loc[mdy[mdy].index] = as_mdy[mdy].to_numpy()
