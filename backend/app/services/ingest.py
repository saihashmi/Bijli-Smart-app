"""Reading uploaded files and detecting which columns hold what."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv": "csv", ".txt": "csv", ".xlsx": "xlsx", ".xlsm": "xlsx"}

ROLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "timestamp": re.compile(r"(date|time|timestamp|datetime|day|period|month|reading.?on|billing)", re.I),
    "consumption": re.compile(r"(kwh|kw\.?h|units?|consumption|energy|usage|used|load|reading|import)", re.I),
    "cost": re.compile(r"(cost|amount|bill|price|charge|payable|rs\b|pkr|inr|usd|tariff.?amount)", re.I),
    "category": re.compile(r"(appliance|device|meter|category|location|room|site|circuit|zone|area|floor|branch|feeder)", re.I),
}

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
_DMY_RE = re.compile(r"^\s*(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})")


class IngestError(ValueError):
    pass


def read_table(path: Path) -> pd.DataFrame:
    """Read a CSV or Excel file as raw text-ish values (no type coercion yet)."""
    kind = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
    if kind is None:
        raise IngestError(f"Unsupported file type '{path.suffix}'. Upload a .csv or .xlsx file.")
    if kind == "csv":
        last_err: Exception | None = None
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                df = pd.read_csv(path, dtype=str, sep=None, engine="python", encoding=enc, skip_blank_lines=False)
                break
            except UnicodeDecodeError as e:
                last_err = e
            except Exception as e:  # malformed CSV
                raise IngestError(f"Could not read CSV: {e}") from e
        else:
            raise IngestError(f"Could not decode CSV: {last_err}")
    else:
        try:
            df = pd.read_excel(path, engine="openpyxl", sheet_name=0)
        except Exception as e:
            raise IngestError(f"Could not read Excel file: {e}") from e
        # Keep native datetimes; turn everything else into object so cleaning controls parsing.
        df = df.astype(object).where(df.notna(), None)

    df.columns = [_clean_header(c, i) for i, c in enumerate(df.columns)]
    df = _dedupe_headers(df)
    if df.shape[1] == 0:
        raise IngestError("The file has no columns.")
    return df


def _clean_header(name: Any, idx: int) -> str:
    text = "" if name is None else str(name)
    text = re.sub(r"\s+", " ", text).strip()
    if not text or text.lower().startswith("unnamed:"):
        text = f"column_{idx + 1}"
    return text


def _dedupe_headers(df: pd.DataFrame) -> pd.DataFrame:
    seen: dict[str, int] = {}
    cols = []
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            cols.append(c)
    df.columns = cols
    return df


# ---------- value parsing ----------

def parse_numeric(series: pd.Series) -> pd.Series:
    """Parse numbers that may carry units, currency symbols or thousands separators ("1,234.5 kWh")."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").astype(float)

    def one(v: Any) -> float:
        if v is None:
            return float("nan")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
        s = str(v).strip()
        if not s or s.lower() in ("nan", "na", "n/a", "null", "none", "-", "--"):
            return float("nan")
        negative = s.startswith("(") and s.endswith(")")
        m = _NUM_RE.search(s.replace(",", ""))
        if not m:
            return float("nan")
        val = float(m.group(0))
        return -abs(val) if negative else val

    return series.map(one).astype(float)


def detect_dayfirst(series: pd.Series, default: bool) -> bool:
    first_gt12 = second_gt12 = False
    for v in series.dropna().astype(str).head(500):
        m = _DMY_RE.match(v)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        first_gt12 |= a > 12
        second_gt12 |= b > 12
    if first_gt12 and not second_gt12:
        return True
    if second_gt12 and not first_gt12:
        return False
    return default


def parse_datetime(series: pd.Series, dayfirst: bool) -> pd.Series:
    """Parse dates/timestamps. Vectorised ISO-8601 first, then a per-format fallback."""
    if pd.api.types.is_datetime64_any_dtype(series):
        out = series.copy()
    else:
        out = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
        native_mask = series.map(lambda v: hasattr(v, "year") and hasattr(v, "month") and not isinstance(v, str))
        if native_mask.any():
            out[native_mask] = pd.to_datetime(series[native_mask], errors="coerce")
        text = series[~native_mask & series.notna()].astype(str).str.strip()
        text = text[~text.str.lower().isin(["", "nan", "nat", "none", "null", "-"])]
        if not text.empty:
            parsed = pd.to_datetime(text, format="ISO8601", errors="coerce")
            rest = parsed.isna()
            if rest.any():
                parsed[rest] = pd.to_datetime(text[rest], format="mixed", dayfirst=dayfirst, errors="coerce")
            out[text.index] = parsed
    if getattr(out.dt, "tz", None) is not None:
        out = out.dt.tz_localize(None)
    return out


# ---------- column role detection ----------

def _parse_rate(series: pd.Series, parser) -> float:
    s = series.dropna()
    s = s[s.astype(str).str.strip() != ""]
    if s.empty:
        return 0.0
    parsed = parser(s.head(500))
    return float(parsed.notna().mean())


def detect_mapping(df: pd.DataFrame, dayfirst_default: bool = True) -> dict[str, Any]:
    """Guess which columns are timestamp / consumption / cost / category. User can override."""
    cols = list(df.columns)
    numeric_rate = {c: _parse_rate(df[c], parse_numeric) for c in cols}
    date_rate: dict[str, float] = {}
    for c in cols:
        sample = df[c]
        dayfirst = detect_dayfirst(sample, dayfirst_default)
        date_rate[c] = _parse_rate(sample, lambda s, d=dayfirst: parse_datetime(s, d))

    def looks_like_plain_number(c: str) -> bool:
        # Pure numbers like 123.4 can be parsed as dates by dateutil; don't treat them as dates.
        s = df[c].dropna().astype(str).head(200)
        return bool(len(s)) and s.str.fullmatch(r"\s*-?[\d,]+(\.\d+)?\s*").mean() > 0.8

    used: set[str] = set()

    def pick(role: str, ok) -> str | None:
        named = [c for c in cols if c not in used and ROLE_PATTERNS[role].search(c) and ok(c)]
        if named:
            used.add(named[0])
            return named[0]
        return None

    ts = pick("timestamp", lambda c: date_rate[c] >= 0.6 and not looks_like_plain_number(c))
    if ts is None:
        cands = [c for c in cols if date_rate[c] >= 0.8 and not looks_like_plain_number(c)]
        if cands:
            ts = cands[0]
            used.add(ts)

    cost = pick("cost", lambda c: numeric_rate[c] >= 0.6)
    consumption = pick("consumption", lambda c: numeric_rate[c] >= 0.6)
    if consumption is None:
        cands = [c for c in cols if c not in used and numeric_rate[c] >= 0.8]
        if cands:
            consumption = cands[0]
            used.add(consumption)

    def is_categorical(c: str) -> bool:
        s = df[c].dropna().astype(str).str.strip()
        s = s[s != ""]
        if s.empty or numeric_rate[c] > 0.5:
            return False
        n = s.nunique()
        return 2 <= n <= min(50, max(2, len(s) // 2))

    category = pick("category", is_categorical)
    if category is None:
        cands = [c for c in cols if c not in used and is_categorical(c)]
        category = cands[0] if cands else None

    dayfirst = detect_dayfirst(df[ts], dayfirst_default) if ts else dayfirst_default
    return {
        "timestamp": ts,
        "consumption": consumption,
        "cost": cost,
        "category": category,
        "dayfirst": dayfirst,
        "confidence": {
            "timestamp": round(date_rate.get(ts, 0.0), 3) if ts else 0.0,
            "consumption": round(numeric_rate.get(consumption, 0.0), 3) if consumption else 0.0,
            "cost": round(numeric_rate.get(cost, 0.0), 3) if cost else 0.0,
        },
    }


def validate_mapping(df: pd.DataFrame, mapping: dict[str, Any]) -> list[str]:
    errors = []
    for role in ("timestamp", "consumption"):
        if not mapping.get(role):
            errors.append(f"Select the {role} column.")
    for role in ("timestamp", "consumption", "cost", "category"):
        col = mapping.get(role)
        if col and col not in df.columns:
            errors.append(f"Column '{col}' (for {role}) is not in the file.")
    chosen = [mapping.get(r) for r in ("timestamp", "consumption", "cost", "category") if mapping.get(r)]
    if len(chosen) != len(set(chosen)):
        errors.append("Each column can be used for only one role.")
    return errors
