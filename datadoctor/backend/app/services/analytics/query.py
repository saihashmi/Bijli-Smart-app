"""The single analytics engine (SPEC FR-4.4 to FR-4.6, §12.2).

Dashboards, the AI Analyst and exports all call `run()`, so the same question always gives the same figure.
Every result carries `meta` saying exactly which rows were used and which were left out, and why.

Rules that are never broken here:
- a missing or non-numeric cell is never treated as zero (it is left out of the calculation and counted);
- an ambiguous or impossible date is never placed in a period (left out and counted);
- a group with no usable values has the value null, not 0.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...errors import AppError
from .typed import MISSING_LABEL, TypedColumn, TypedFrame

Agg = Literal["count", "sum", "avg", "min", "max", "median", "distinct"]
Grain = Literal["day", "week", "month", "quarter", "year"]

MAX_POINTS = 500
MAX_SERIES = 12
SCATTER_SAMPLE = 2000
OTHER_LABEL = "Other"

AGG_LABEL = {
    "count": "Count",
    "sum": "Sum",
    "avg": "Average",
    "min": "Minimum",
    "max": "Maximum",
    "median": "Median",
    "distinct": "Distinct count",
}

# Which aggregations make sense for which kind of column (shared with the frontend through /analytics/fields).
AGGS_BY_KIND: dict[str, list[str]] = {
    "number": ["sum", "avg", "median", "min", "max", "count", "distinct"],
    "date": ["count", "distinct", "min", "max"],
    "boolean": ["count", "distinct"],
    "category": ["count", "distinct"],
    "text": ["count", "distinct"],
    "other": ["count"],
    "empty": [],
}


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InFilter(_M):
    op: Literal["in", "not_in"]
    column: str
    values: list[str] = Field(max_length=500)
    include_missing: bool = False


class RangeFilter(_M):
    op: Literal["range"]
    column: str
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _some_bound(self) -> RangeFilter:
        if self.min is None and self.max is None:
            raise ValueError("give a minimum, a maximum or both")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("minimum is greater than maximum")
        return self


class DateRangeFilter(_M):
    op: Literal["date_range"]
    column: str
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def _some_bound(self) -> DateRangeFilter:
        if self.start is None and self.end is None:
            raise ValueError("give a start date, an end date or both")
        if self.start and self.end and self.start > self.end:
            raise ValueError("start date is after end date")
        return self


Filter = Annotated[InFilter | RangeFilter | DateRangeFilter, Field(discriminator="op")]


class Measure(_M):
    agg: Agg = "count"
    column: str | None = None  # None is only valid for count (= number of rows)


class Dimension(_M):
    column: str
    grain: Grain | None = None  # required for date columns, not allowed otherwise


class Sort(_M):
    by: Literal["value", "label"] = "value"
    dir: Literal["asc", "desc"] = "desc"


class AggregateQuery(_M):
    """KPI (no dimension), grouped series (dimension) or grouped multi-series (dimension + series)."""

    kind: Literal["aggregate"] = "aggregate"
    measure: Measure = Field(default_factory=Measure)
    dimension: Dimension | None = None
    series: str | None = None
    filters: list[Filter] = Field(default_factory=list, max_length=20)
    sort: Sort | None = None
    limit: int | None = Field(default=None, ge=1, le=MAX_POINTS)
    other: bool = True  # group everything beyond `limit` as "Other" instead of dropping it


class HistogramQuery(_M):
    kind: Literal["histogram"]
    column: str
    bins: int = Field(default=20, ge=2, le=60)
    filters: list[Filter] = Field(default_factory=list, max_length=20)


class ScatterQuery(_M):
    kind: Literal["scatter"]
    x: str
    y: str
    filters: list[Filter] = Field(default_factory=list, max_length=20)


class TableQuery(_M):
    kind: Literal["table"]
    columns: list[str] = Field(default_factory=list, max_length=30)  # empty = first 8 columns
    filters: list[Filter] = Field(default_factory=list, max_length=20)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=25, ge=1, le=200)


Query = Annotated[AggregateQuery | HistogramQuery | ScatterQuery | TableQuery, Field(discriminator="kind")]


# ---------- helpers ----------
def _bad(code: str, message: str) -> AppError:
    return AppError(422, code, message)


def _col(tf: TypedFrame, name: str) -> TypedColumn:
    if not tf.has(name):
        raise _bad("UNKNOWN_COLUMN", f"Unknown column: {name}")
    return tf.col(name)


def _num(x: Any) -> float | int | None:
    """JSON-safe number: NaN/inf become null, whole floats stay floats only when large."""
    if x is None:
        return None
    x = float(x)
    if not np.isfinite(x):
        return None
    return int(x) if x.is_integer() and abs(x) < 2**53 else x


def _iso(ts: Any, with_time: bool = False) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    t = pd.Timestamp(ts)
    return t.isoformat(sep=" ", timespec="seconds") if with_time and (t.hour or t.minute or t.second) else str(t.date())


def apply_filters(tf: TypedFrame, filters: list[Any]) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Row mask for the filters, plus a description of each one (how many rows it kept on its own)."""
    mask = np.ones(len(tf), dtype=bool)
    described = []
    for f in filters:
        c = _col(tf, f.column)
        if isinstance(f, InFilter):
            wanted = set(f.values)
            hit_codes = np.array([i for i, lab in enumerate(c.labels) if lab in wanted], dtype=np.int64)
            m = np.isin(c.codes, hit_codes)
            if f.include_missing:
                m |= c.missing
            if f.op == "not_in":
                m = ~m
            unknown = sorted(wanted - set(c.labels))[:5]
            info: dict[str, Any] = {"values": f.values, "include_missing": f.include_missing}
            if unknown:
                info["values_not_in_data"] = unknown
        elif isinstance(f, RangeFilter):
            if c.kind != "number":
                raise _bad("FILTER_NOT_NUMERIC", f"A number range needs a numeric column; “{c.name}” is {c.kind}.")
            m = ~np.isnan(c.numbers)
            if f.min is not None:
                m &= c.numbers >= f.min
            if f.max is not None:
                m &= c.numbers <= f.max
            info = {"min": f.min, "max": f.max}
        else:
            if c.kind != "date":
                raise _bad("FILTER_NOT_DATE", f"A date range needs a date column; “{c.name}” is {c.kind}.")
            m = ~np.isnat(c.dates)
            if f.start is not None:
                m &= c.dates >= np.datetime64(f.start)
            if f.end is not None:
                m &= c.dates < np.datetime64(f.end) + np.timedelta64(1, "D")  # end date is inclusive
            info = {"start": str(f.start) if f.start else None, "end": str(f.end) if f.end else None}
        described.append({"op": f.op, "column": f.column, **info, "rows_matching": int(m.sum())})
        mask &= m
    return mask, described


def _check_measure(tf: TypedFrame, m: Measure) -> TypedColumn | None:
    if m.column is None:
        if m.agg != "count":
            raise _bad("MEASURE_NEEDS_COLUMN", f"{AGG_LABEL[m.agg]} needs a column.")
        return None
    c = _col(tf, m.column)
    if m.agg not in AGGS_BY_KIND[c.kind]:
        allowed = ", ".join(AGG_LABEL[a].lower() for a in AGGS_BY_KIND[c.kind]) or "nothing (the column is empty)"
        raise _bad(
            "AGGREGATION_NOT_ALLOWED",
            f"{AGG_LABEL[m.agg]} cannot be used on “{c.name}” ({c.kind}). Allowed: {allowed}.",
        )
    return c


def _period(dates: np.ndarray, grain: str) -> tuple[np.ndarray, list[str], list[str]]:
    """Bucket dates. Returns (code per row, -1 where no date), sortable keys, display labels (chronological)."""
    ok = ~np.isnat(dates)
    idx = pd.DatetimeIndex(dates[ok])
    if grain == "day":
        start = idx.normalize()
    elif grain == "week":
        start = (idx - pd.to_timedelta(idx.weekday, unit="D")).normalize()  # weeks start on Monday
    elif grain == "month":
        start = idx.to_period("M").start_time
    elif grain == "quarter":
        start = idx.to_period("Q").start_time
    else:
        start = idx.to_period("Y").start_time
    uniq = np.sort(start.unique())
    codes = np.full(len(dates), -1, dtype=np.int64)
    codes[ok] = np.searchsorted(uniq, start.to_numpy())
    keys = [str(pd.Timestamp(u).date()) for u in uniq]
    labels = []
    for u in uniq:
        t = pd.Timestamp(u)
        if grain == "day":
            labels.append(str(t.date()))
        elif grain == "week":
            labels.append(f"Week of {t.date()}")
        elif grain == "month":
            labels.append(t.strftime("%Y-%m"))
        elif grain == "quarter":
            labels.append(f"{t.year}-Q{(t.month - 1) // 3 + 1}")
        else:
            labels.append(str(t.year))
    return codes, keys, labels


def _reduce(agg: str, mc: TypedColumn | None, rows: np.ndarray) -> tuple[Any, int]:
    """Aggregate the measure over the given row positions. Returns (value, cells used)."""
    if mc is None:
        return int(len(rows)), int(len(rows))
    if agg == "count":
        used = int((~mc.missing[rows]).sum())
        return used, used
    if agg == "distinct":
        codes = mc.codes[rows]
        codes = codes[codes >= 0]
        return int(len(np.unique(codes))), int(len(codes))
    if mc.kind == "date":
        d = mc.dates[rows]
        d = d[~np.isnat(d)]
        if not len(d):
            return None, 0
        return _iso(d.min() if agg == "min" else d.max(), mc.has_time), int(len(d))
    v = mc.numbers[rows]
    v = v[~np.isnan(v)]
    if not len(v):
        return None, 0
    fn = {"sum": np.sum, "avg": np.mean, "min": np.min, "max": np.max, "median": np.median}[agg]
    return _num(fn(v)), int(len(v))


def _measure_meta(mc: TypedColumn | None, agg: str, mask: np.ndarray) -> dict[str, Any]:
    if mc is None:
        return {}
    present = ~mc.missing
    out = {"measure_missing": int((mask & mc.missing).sum())}
    if agg in ("sum", "avg", "min", "max", "median"):
        usable = ~np.isnan(mc.numbers) if mc.kind == "number" else ~np.isnat(mc.dates)
        out["measure_not_usable"] = int((mask & present & ~usable).sum())
    return out


def _measure_label(m: Measure) -> str:
    return "Number of rows" if m.column is None else f"{AGG_LABEL[m.agg]} of {m.column}"


# ---------- aggregate ----------
def _aggregate(tf: TypedFrame, q: AggregateQuery) -> dict[str, Any]:
    mc = _check_measure(tf, q.measure)
    mask, filters = apply_filters(tf, q.filters)
    agg = q.measure.agg
    meta: dict[str, Any] = {
        "rows_total": len(tf),
        "rows_after_filters": int(mask.sum()),
        "filters": filters,
        **_measure_meta(mc, agg, mask),
    }
    all_rows = np.flatnonzero(mask)
    total_value, total_n = _reduce(agg, mc, all_rows)
    result: dict[str, Any] = {
        "kind": "aggregate",
        "measure": {"agg": agg, "column": q.measure.column, "label": _measure_label(q.measure)},
        "dimension": None,
        "series": None,
        "rows": [],
        "total": {"value": total_value, "n": total_n},
        "meta": meta,
    }
    if q.dimension is None:
        if q.series:
            raise _bad("SERIES_NEEDS_DIMENSION", "A series split needs a category or date to group by first.")
        return result

    # --- dimension ---
    dc = _col(tf, q.dimension.column)
    is_date = dc.kind == "date"
    if is_date:
        if q.dimension.grain is None:
            raise _bad("GRAIN_REQUIRED", f"“{dc.name}” is a date: choose day, week, month, quarter or year.")
        codes, keys, labels = _period(dc.dates, q.dimension.grain)
        unusable = mask & ~dc.missing & (codes < 0)
        meta["dimension_not_dated"] = int(unusable.sum())  # text, ambiguous or impossible dates: in no period
        meta["dimension_missing"] = int((mask & dc.missing).sum())
        in_dim = mask & (codes >= 0)
    else:
        if q.dimension.grain is not None:
            raise _bad("GRAIN_NOT_ALLOWED", f"A date grain only applies to date columns; “{dc.name}” is {dc.kind}.")
        codes, labels = dc.codes.copy(), list(dc.labels)
        keys = list(labels)
        n_missing = int((mask & dc.missing).sum())
        meta["dimension_missing"] = n_missing
        if n_missing:  # missing values form their own, clearly named group
            codes[dc.missing] = len(labels)
            labels.append(MISSING_LABEL)
            keys.append("")
        in_dim = mask & (codes >= 0)

    rows_idx = np.flatnonzero(in_dim)
    row_codes = codes[rows_idx]
    order = np.argsort(row_codes, kind="stable")
    rows_sorted, codes_sorted = rows_idx[order], row_codes[order]
    present_codes, starts = np.unique(codes_sorted, return_index=True)
    bounds = list(starts) + [len(rows_sorted)]
    groups = {int(c): rows_sorted[bounds[i] : bounds[i + 1]] for i, c in enumerate(present_codes)}
    meta["groups_total"] = len(groups)

    missing_code = len(labels) - 1 if (not is_date and labels and labels[-1] == MISSING_LABEL) else None
    items = []
    for code, grp in groups.items():
        value, n = _reduce(agg, mc, grp)
        items.append(
            {
                "key": keys[code],
                "label": labels[code],
                "value": value,
                "n": n,
                "rows": int(len(grp)),
                "missing": code == missing_code,
                "_rows": grp,
                "_code": code,
            }
        )

    sort = q.sort or Sort(by="label", dir="asc") if is_date else q.sort or Sort()
    reverse = sort.dir == "desc"
    if sort.by == "label":
        if is_date:
            items.sort(key=lambda r: r["key"], reverse=reverse)
        elif dc.kind == "number":
            items.sort(key=lambda r: (r["missing"], _as_float(r["label"])), reverse=reverse)
        else:
            items.sort(key=lambda r: (r["missing"], r["label"].casefold(), r["label"]), reverse=reverse)
    else:
        # Groups without a value go last whichever direction is chosen; ties keep label order.
        items.sort(key=lambda r: r["label"].casefold())
        valued = [r for r in items if r["value"] is not None]
        empty = [r for r in items if r["value"] is None]
        valued.sort(key=lambda r: r["value"], reverse=reverse)
        items = valued + empty

    limit = min(q.limit or MAX_POINTS, MAX_POINTS)
    meta["other_groups"] = 0
    if len(items) > limit:
        if q.limit is None:
            meta["capped"] = True  # hit the hard cap without the user choosing a limit
        keep, rest = items[: limit - 1 if q.other else limit], items[limit - 1 if q.other else limit :]
        meta["other_groups"] = len(rest)
        meta["other_included"] = q.other
        if q.other:
            rest_rows = np.concatenate([r["_rows"] for r in rest])
            value, n = _reduce(agg, mc, rest_rows)
            keep.append(
                {
                    "key": "__other__",
                    "label": f"{OTHER_LABEL} ({len(rest)} groups)",
                    "value": value,
                    "n": n,
                    "rows": int(len(rest_rows)),
                    "missing": False,
                    "other": True,
                    "_rows": rest_rows,
                    "_code": -2,
                }
            )
        items = keep

    result["dimension"] = {"column": dc.name, "kind": dc.kind, "grain": q.dimension.grain}

    # --- optional series split ---
    if q.series:
        sc = _col(tf, q.series)
        if sc.name == dc.name:
            raise _bad("SERIES_SAME_AS_DIMENSION", "Choose a different column for the series split.")
        s_codes, s_labels = sc.codes.copy(), list(sc.labels)
        if (in_dim & sc.missing).any():
            s_codes[sc.missing] = len(s_labels)
            s_labels.append(MISSING_LABEL)
        present_s, counts = np.unique(s_codes[rows_idx], return_counts=True)
        ranked = [int(c) for c in present_s[np.argsort(-counts, kind="stable")]]  # biggest series first
        kept_s = ranked[: MAX_SERIES - 1] if len(ranked) > MAX_SERIES else ranked
        other_s = ranked[len(kept_s) :] if len(ranked) > MAX_SERIES else []
        names = [s_labels[c] for c in kept_s] + ([f"{OTHER_LABEL} ({len(other_s)} series)"] if other_s else [])
        meta["series_total"] = len(ranked)
        meta["series_other"] = len(other_s)
        kept_set = np.array(kept_s, dtype=np.int64)
        for r in items:
            grp = r["_rows"]
            g_codes = s_codes[grp]
            values: dict[str, Any] = {}
            for c, name in zip(kept_s, names, strict=False):
                values[name] = _reduce(agg, mc, grp[g_codes == c])[0] if (g_codes == c).any() else None
            if other_s:
                rest_mask = ~np.isin(g_codes, kept_set)
                values[names[-1]] = _reduce(agg, mc, grp[rest_mask])[0] if rest_mask.any() else None
            r["values"] = values
        result["series"] = {"column": sc.name, "names": names}

    for r in items:
        r.pop("_rows")
        r.pop("_code")
    result["rows"] = items
    return result


def _as_float(label: str) -> float:
    try:
        return float(label)
    except ValueError:
        return float("inf")


# ---------- histogram ----------
def _histogram(tf: TypedFrame, q: HistogramQuery) -> dict[str, Any]:
    c = _col(tf, q.column)
    if c.kind != "number":
        raise _bad("NOT_NUMERIC", f"A histogram needs a numeric column; “{c.name}” is {c.kind}.")
    mask, filters = apply_filters(tf, q.filters)
    usable = mask & ~np.isnan(c.numbers)
    v = c.numbers[usable]
    meta = {
        "rows_total": len(tf),
        "rows_after_filters": int(mask.sum()),
        "filters": filters,
        "values_used": int(len(v)),
        "measure_missing": int((mask & c.missing).sum()),
        "measure_not_usable": int((mask & ~c.missing & np.isnan(c.numbers)).sum()),
    }
    bins: list[dict[str, Any]] = []
    stats = None
    if len(v):
        lo, hi = float(v.min()), float(v.max())
        if lo == hi:
            bins = [{"start": _num(lo), "end": _num(hi), "count": int(len(v))}]
        else:
            counts, edges = np.histogram(v, bins=q.bins, range=(lo, hi))
            bins = [{"start": _num(edges[i]), "end": _num(edges[i + 1]), "count": int(n)} for i, n in enumerate(counts)]
        q1, med, q3 = np.quantile(v, [0.25, 0.5, 0.75])
        stats = {
            "min": _num(lo),
            "max": _num(hi),
            "mean": _num(v.mean()),
            "median": _num(med),
            "q1": _num(q1),
            "q3": _num(q3),
            "std": _num(v.std(ddof=1)) if len(v) > 1 else None,
        }
    return {"kind": "histogram", "column": c.name, "bins": bins, "stats": stats, "meta": meta}


# ---------- scatter ----------
def _scatter(tf: TypedFrame, q: ScatterQuery) -> dict[str, Any]:
    xc, yc = _col(tf, q.x), _col(tf, q.y)
    for c in (xc, yc):
        if c.kind != "number":
            raise _bad("NOT_NUMERIC", f"A scatter plot needs two numeric columns; “{c.name}” is {c.kind}.")
    if xc.name == yc.name:
        raise _bad("SAME_COLUMN", "Choose two different columns.")
    mask, filters = apply_filters(tf, q.filters)
    both = mask & ~np.isnan(xc.numbers) & ~np.isnan(yc.numbers)
    idx = np.flatnonzero(both)
    x, y = xc.numbers[idx], yc.numbers[idx]
    n = int(len(idx))
    r = None
    if n >= 3 and x.std() > 0 and y.std() > 0:
        r = _num(np.corrcoef(x, y)[0, 1])  # on ALL usable pairs, not on the sample
    sampled = n > SCATTER_SAMPLE
    if sampled:
        pick = np.sort(np.random.default_rng(0).choice(n, SCATTER_SAMPLE, replace=False))  # fixed seed: repeatable
        x, y = x[pick], y[pick]
    return {
        "kind": "scatter",
        "x": xc.name,
        "y": yc.name,
        "points": [[_num(a), _num(b)] for a, b in zip(x, y, strict=True)],
        "pearson_r": r,
        "meta": {
            "rows_total": len(tf),
            "rows_after_filters": int(mask.sum()),
            "filters": filters,
            "pairs_used": n,
            "pairs_left_out": int(mask.sum()) - n,  # either value missing or not a number
            "sampled": sampled,
            "points_shown": int(len(x)),
        },
    }


# ---------- table ----------
def _table(tf: TypedFrame, q: TableQuery, header_row: int) -> dict[str, Any]:
    from ..ingest.workbook import display_value

    cols = q.columns or tf.columns[:8]
    for name in cols:
        if not tf.has(name):
            raise _bad("UNKNOWN_COLUMN", f"Unknown column: {name}")
    mask, filters = apply_filters(tf, q.filters)
    idx = np.flatnonzero(mask)
    page = idx[q.offset : q.offset + q.limit]
    part = tf.df.iloc[page][cols]
    return {
        "kind": "table",
        "columns": cols,
        "rows": [[display_value(v) for v in row] for row in part.itertuples(index=False, name=None)],
        "row_numbers": [int(i) + header_row + 2 for i in part.index],
        "offset": q.offset,
        "total": int(len(idx)),
        "meta": {"rows_total": len(tf), "rows_after_filters": int(len(idx)), "filters": filters},
    }


def run(tf: TypedFrame, q: Any, header_row: int = 0) -> dict[str, Any]:
    if isinstance(q, AggregateQuery):
        return _aggregate(tf, q)
    if isinstance(q, HistogramQuery):
        return _histogram(tf, q)
    if isinstance(q, ScatterQuery):
        return _scatter(tf, q)
    return _table(tf, q, header_row)
