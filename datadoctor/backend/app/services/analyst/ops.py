"""The allowlisted analytical operations of the AI Analyst (SPEC §12.2).

This is the ONLY way a question can act on data: an operation name from `OPERATIONS` plus parameters validated by
pydantic against the real columns. No generated code or SQL exists anywhere in this path. Every figure comes from
the shared analytics engine or the stored profile, and the local explanation is a template filled with those
figures, so it cannot contain a number that was not calculated.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ...errors import AppError
from ..analytics import query as aq
from ..analytics.recommend import recommend
from ..analytics.typed import TypedFrame

Agg = Literal["count", "sum", "avg", "min", "max", "median", "distinct"]
Grain = Literal["day", "week", "month", "quarter", "year"]


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CountRows(_P):
    filters: list[aq.Filter] = Field(default_factory=list, max_length=10)


class Aggregate(_P):
    measure: str
    agg: Agg = "sum"
    filters: list[aq.Filter] = Field(default_factory=list, max_length=10)


class GroupRank(_P):
    group_by: str
    measure: str | None = None
    agg: Agg = "count"
    order: Literal["desc", "asc"] = "desc"
    top_n: int = Field(default=10, ge=1, le=50)
    filters: list[aq.Filter] = Field(default_factory=list, max_length=10)


class TimeTrend(_P):
    date_col: str
    grain: Grain = "month"
    measure: str | None = None
    agg: Agg = "count"
    filters: list[aq.Filter] = Field(default_factory=list, max_length=10)


class ExtremePeriod(_P):
    date_col: str
    grain: Grain = "month"
    measure: str | None = None
    agg: Agg = "count"
    which: Literal["max", "min"] = "max"


class CompareGroups(_P):
    group_by: str
    values: list[str] = Field(min_length=2, max_length=5)
    measure: str | None = None
    agg: Agg = "count"


class Distribution(_P):
    column: str
    bins: int = Field(default=20, ge=2, le=60)


class Correlation(_P):
    x: str
    y: str


class NoParams(_P):
    pass


class DuplicateSummary(_P):
    key_columns: list[str] = Field(default_factory=list, max_length=10)


class ColumnProfile(_P):
    column: str


class OutlierSummary(_P):
    column: str


class QualityExplain(_P):
    codes: list[str] = Field(default_factory=list, max_length=16)


OPERATIONS: dict[str, dict[str, Any]] = {
    "count_rows": {"model": CountRows, "title": "Count rows", "example": "How many records are there?"},
    "aggregate": {"model": Aggregate, "title": "Calculate one figure", "example": "What is the total amount?"},
    "group_rank": {"model": GroupRank, "title": "Rank groups", "example": "Which category has the most records?"},
    "time_trend": {"model": TimeTrend, "title": "Trend over time", "example": "Show the trend over time."},
    "extreme_period": {
        "model": ExtremePeriod,
        "title": "Highest or lowest period",
        "example": "Which month has the highest total?",
    },
    "compare_groups": {"model": CompareGroups, "title": "Compare groups", "example": "Compare two departments."},
    "distribution": {
        "model": Distribution,
        "title": "Distribution of a number",
        "example": "How are amounts distributed?",
    },
    "correlation": {
        "model": Correlation,
        "title": "Relationship between two numbers",
        "example": "Is age related to amount?",
    },
    "missing_summary": {
        "model": NoParams,
        "title": "Missing values",
        "example": "Which columns contain missing values?",
    },
    "duplicate_summary": {"model": DuplicateSummary, "title": "Duplicates", "example": "Are there duplicates?"},
    "column_profile": {"model": ColumnProfile, "title": "Describe a column", "example": "Describe the Region column."},
    "outlier_summary": {"model": OutlierSummary, "title": "Unusual values", "example": "Explain the anomalies."},
    "chart_suggestions": {
        "model": NoParams,
        "title": "Chart suggestions",
        "example": "Suggest the best charts for this dataset.",
    },
    "quality_explain": {"model": QualityExplain, "title": "Explain data quality", "example": "Why is my score low?"},
}

AGG_WORD = {
    "count": "count",
    "sum": "total",
    "avg": "average",
    "min": "minimum",
    "max": "maximum",
    "median": "median",
    "distinct": "number of distinct values",
}


def fmt(v: Any) -> str:
    """How a computed value is written in explanations. The verifier accepts exactly these spellings."""
    if v is None:
        return "no value"
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return str(v)
    if float(v).is_integer():
        return f"{int(v):,}"
    return f"{v:,.2f}"


def _measure(measure: str | None, agg: str) -> dict[str, Any]:
    return {"agg": agg, "column": measure} if measure else {"agg": "count"}


def _what(measure: str | None, agg: str) -> str:
    return "number of rows" if not measure else f"{AGG_WORD[agg]} of “{measure}”"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]  # str.capitalize() would lower-case the column name


def _notes(meta: dict[str, Any], measure: str | None = None, dim: str | None = None) -> list[str]:
    notes = []
    if meta.get("rows_after_filters", 0) < meta.get("rows_total", 0):
        notes.append(f"Filters keep {fmt(meta['rows_after_filters'])} of {fmt(meta['rows_total'])} rows.")
    if meta.get("measure_missing"):
        notes.append(f"{fmt(meta['measure_missing'])} rows have no value in “{measure}” and are not counted as zero.")
    if meta.get("measure_not_usable"):
        notes.append(f"{fmt(meta['measure_not_usable'])} values in “{measure}” are not numbers and are left out.")
    if meta.get("dimension_not_dated"):
        notes.append(
            f"{fmt(meta['dimension_not_dated'])} rows have an unclear or impossible date in “{dim}” and are in no period."
        )
    if meta.get("other_groups"):
        notes.append(f"{fmt(meta['other_groups'])} further groups are not listed.")
    return notes


def _answer(op: str, params: _P, text: str, **extra: Any) -> dict[str, Any]:
    return {
        "operation": op,
        "params": params.model_dump(mode="json", exclude_defaults=False),
        "title": OPERATIONS[op]["title"],
        "answer": text,
        "table": None,
        "chart": None,
        "notes": [],
        **extra,
    }


def _table(columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {"columns": columns, "rows": [[fmt(c) if not isinstance(c, str) else c for c in r] for r in rows]}


def columns_used(op: str, p: _P) -> list[str]:
    used: list[str] = []
    for key in ("measure", "group_by", "date_col", "column", "x", "y"):
        v = getattr(p, key, None)
        if v:
            used.append(v)
    used += list(getattr(p, "key_columns", []) or [])
    used += [f.column for f in getattr(p, "filters", [])]
    return used


def validate(op: str, params: dict[str, Any]) -> _P:
    if op not in OPERATIONS:
        raise AppError(422, "UNSUPPORTED_OPERATION", "That operation is not supported.")
    try:
        return OPERATIONS[op]["model"].model_validate(params)
    except Exception:
        raise AppError(
            422, "INVALID_PARAMETERS", f"The parameters for “{OPERATIONS[op]['title']}” are not valid."
        ) from None


def execute(op: str, p: _P, tf: TypedFrame, profile: dict[str, Any], sensitive: list[str]) -> dict[str, Any]:
    """Run one validated operation. Raises AppError(422) with a plain message when it does not fit the data."""
    for name in columns_used(op, p):
        if not tf.has(name):
            raise AppError(422, "UNKNOWN_COLUMN", f"There is no column called “{name}”.")
    return _RUN[op](p, tf, profile, sensitive)


# ---------- operations ----------
def _count_rows(p: CountRows, tf: TypedFrame, *_: Any) -> dict[str, Any]:
    res = aq.run(tf, aq.AggregateQuery(filters=p.filters))
    n, total = res["total"]["value"], res["meta"]["rows_total"]
    text = f"There are {fmt(n)} rows." if not p.filters else f"{fmt(n)} of {fmt(total)} rows match the filters."
    return _answer("count_rows", p, text, notes=[])


def _aggregate(p: Aggregate, tf: TypedFrame, *_: Any) -> dict[str, Any]:
    res = aq.run(tf, aq.AggregateQuery(measure=aq.Measure(agg=p.agg, column=p.measure), filters=p.filters))
    v, n = res["total"]["value"], res["total"]["n"]
    if v is None:
        text = f"“{p.measure}” has no usable values, so the {AGG_WORD[p.agg]} cannot be calculated."
    else:
        text = f"The {AGG_WORD[p.agg]} of “{p.measure}” is {fmt(v)}, calculated from {fmt(n)} values."
    return _answer("aggregate", p, text, notes=_notes(res["meta"], p.measure))


def _group_rank(p: GroupRank, tf: TypedFrame, *_: Any) -> dict[str, Any]:
    q = aq.AggregateQuery(
        measure=aq.Measure(**_measure(p.measure, p.agg)),
        dimension=aq.Dimension(column=p.group_by),
        sort=aq.Sort(by="value", dir=p.order),
        limit=p.top_n,
        other=False,
        filters=p.filters,
    )
    res = aq.run(tf, q)
    rows = [r for r in res["rows"] if r["value"] is not None]
    what = _what(p.measure, p.agg)
    if not rows:
        text = f"No group of “{p.group_by}” has a usable value for the {what}."
    else:
        lead = rows[0]
        word = "highest" if p.order == "desc" else "lowest"
        tied = [r["label"] for r in rows if r["value"] == lead["value"]]
        if len(tied) > 1:
            text = f"{len(tied)} groups of “{p.group_by}” share the {word} {what} ({fmt(lead['value'])}): {', '.join(tied)}."
        else:
            text = f"“{lead['label']}” has the {word} {what} among “{p.group_by}” groups: {fmt(lead['value'])}."
        text += f" {fmt(res['meta']['groups_total'])} groups were compared."
    return _answer(
        "group_rank",
        p,
        text,
        table=_table([p.group_by, _cap(what), "Rows"], [[r["label"], r["value"], r["rows"]] for r in res["rows"]]),
        chart={"chart": "bar", "result": res} if rows else None,
        notes=_notes(res["meta"], p.measure, p.group_by),
    )


def _series(p: Any, tf: TypedFrame) -> dict[str, Any]:
    c = tf.col(p.date_col)
    if c.kind != "date":
        raise AppError(422, "NOT_A_DATE", f"“{p.date_col}” is not a date column, so it cannot be used for periods.")
    return aq.run(
        tf,
        aq.AggregateQuery(
            measure=aq.Measure(**_measure(p.measure, p.agg)),
            dimension=aq.Dimension(column=p.date_col, grain=p.grain),
            filters=getattr(p, "filters", []),
        ),
    )


def _time_trend(p: TimeTrend, tf: TypedFrame, *_: Any) -> dict[str, Any]:
    res = _series(p, tf)
    rows = [r for r in res["rows"] if isinstance(r["value"], (int, float))]
    what = _what(p.measure, p.agg)
    if len(rows) < 2:
        text = f"There are not enough dated {p.grain}s with values to show a trend ({len(rows)} found)."
    else:
        first, last = rows[0], rows[-1]
        hi = max(rows, key=lambda r: r["value"])
        lo = min(rows, key=lambda r: r["value"])
        if last["value"] > first["value"]:
            move = "higher than"
        elif last["value"] < first["value"]:
            move = "lower than"
        else:
            move = "the same as"
        text = (
            f"The {what} per {p.grain} covers {len(rows)} periods, from {first['label']} ({fmt(first['value'])}) to "
            f"{last['label']} ({fmt(last['value'])}). The last period is {move} the first. "
            f"Highest: {hi['label']} ({fmt(hi['value'])}). Lowest: {lo['label']} ({fmt(lo['value'])}). "
            "This describes the recorded periods only; it is not a forecast."
        )
    return _answer(
        "time_trend",
        p,
        text,
        table=_table(
            [p.grain.capitalize(), _cap(what), "Rows"],
            [[r["label"], r["value"], r["rows"]] for r in res["rows"]],
        ),
        chart={"chart": "line", "result": res} if len(rows) >= 2 else None,
        notes=_notes(res["meta"], p.measure, p.date_col),
    )


def _extreme_period(p: ExtremePeriod, tf: TypedFrame, *_: Any) -> dict[str, Any]:
    res = _series(p, tf)
    rows = [r for r in res["rows"] if isinstance(r["value"], (int, float))]
    what = _what(p.measure, p.agg)
    word = "highest" if p.which == "max" else "lowest"
    if not rows:
        text = f"No {p.grain} has a usable value for the {what}."
    else:
        pick = (max if p.which == "max" else min)(rows, key=lambda r: r["value"])
        tied = [r["label"] for r in rows if r["value"] == pick["value"]]
        if len(tied) > 1:
            text = f"{len(tied)} {p.grain}s share the {word} {what} ({fmt(pick['value'])}): {', '.join(tied)}."
        else:
            text = f"{pick['label']} has the {word} {what}: {fmt(pick['value'])}, out of {len(rows)} {p.grain}s with values."
    return _answer(
        "extreme_period",
        p,
        text,
        table=_table(
            [p.grain.capitalize(), _cap(what), "Rows"],
            [[r["label"], r["value"], r["rows"]] for r in res["rows"]],
        ),
        chart={"chart": "bar", "result": res} if rows else None,
        notes=_notes(res["meta"], p.measure, p.date_col),
    )


def _compare_groups(p: CompareGroups, tf: TypedFrame, *_: Any) -> dict[str, Any]:
    c = tf.col(p.group_by)
    unknown = [v for v in p.values if v not in c.labels]
    if unknown:
        raise AppError(422, "UNKNOWN_VALUE", f"“{unknown[0]}” does not appear in “{p.group_by}”.")
    res = aq.run(
        tf,
        aq.AggregateQuery(
            measure=aq.Measure(**_measure(p.measure, p.agg)),
            dimension=aq.Dimension(column=p.group_by),
            filters=[aq.InFilter(op="in", column=p.group_by, values=p.values)],
            sort=aq.Sort(by="value", dir="desc"),
        ),
    )
    what = _what(p.measure, p.agg)
    parts = [f"“{r['label']}”: {fmt(r['value'])}" for r in res["rows"]]
    valued = [r for r in res["rows"] if isinstance(r["value"], (int, float))]
    text = f"The {what} by “{p.group_by}”: " + "; ".join(parts) + "."
    if len(valued) >= 2 and valued[0]["value"] != valued[-1]["value"]:
        diff = valued[0]["value"] - valued[-1]["value"]
        text += f" “{valued[0]['label']}” is higher than “{valued[-1]['label']}” by {fmt(diff)}."
    meta = dict(res["meta"])
    meta["rows_after_filters"] = meta["rows_total"]  # the value filter is the comparison itself, not a user filter
    return _answer(
        "compare_groups",
        p,
        text,
        table=_table([p.group_by, _cap(what), "Rows"], [[r["label"], r["value"], r["rows"]] for r in res["rows"]]),
        chart={"chart": "bar", "result": res},
        notes=_notes(meta, p.measure, p.group_by),
    )


def _distribution(p: Distribution, tf: TypedFrame, *_: Any) -> dict[str, Any]:
    res = aq.run(tf, aq.HistogramQuery(kind="histogram", column=p.column, bins=p.bins))
    s = res["stats"]
    if not s:
        text = f"“{p.column}” has no numeric values."
    else:
        text = (
            f"“{p.column}” has {fmt(res['meta']['values_used'])} numeric values from {fmt(s['min'])} to {fmt(s['max'])}. "
            f"The median is {fmt(s['median'])} and the average is {fmt(s['mean'])}. "
            f"Half of the values lie between {fmt(s['q1'])} and {fmt(s['q3'])}."
        )
    return _answer(
        "distribution",
        p,
        text,
        chart={"chart": "histogram", "result": res} if s else None,
        notes=_notes(res["meta"], p.column),
    )


def _strength(r: float) -> str:
    a = abs(r)
    if a < 0.1:
        return "no clear linear relationship"
    size = "weak" if a < 0.3 else "moderate" if a < 0.6 else "strong"
    return f"a {size} {'positive' if r > 0 else 'negative'} linear relationship"


def _correlation(p: Correlation, tf: TypedFrame, *_: Any) -> dict[str, Any]:
    res = aq.run(tf, aq.ScatterQuery(kind="scatter", x=p.x, y=p.y))
    r, n = res["pearson_r"], res["meta"]["pairs_used"]
    if r is None:
        text = f"A correlation between “{p.x}” and “{p.y}” cannot be calculated from {fmt(n)} usable rows."
    else:
        text = (
            f"The Pearson correlation between “{p.x}” and “{p.y}” is {r:.2f}, based on {fmt(n)} rows that have both "
            f"values. That is {_strength(r)}. A correlation does not show that one causes the other."
        )
    notes = []
    if res["meta"]["pairs_left_out"]:
        notes.append(
            f"{fmt(res['meta']['pairs_left_out'])} rows lack a number in one of the two columns and are left out."
        )
    if res["meta"]["sampled"]:
        notes.append(
            f"The chart shows a random sample of {fmt(res['meta']['points_shown'])} points. The correlation uses all rows."
        )
    return _answer("correlation", p, text, chart={"chart": "scatter", "result": res} if n else None, notes=notes)


def _missing_summary(p: NoParams, tf: TypedFrame, profile: dict[str, Any], *_: Any) -> dict[str, Any]:
    cols = sorted((c for c in profile["column_profiles"] if c["missing"]), key=lambda c: -c["missing"])
    if not cols:
        text = f"No column has missing values. All {fmt(profile['total_cells'])} cells are filled."
    else:
        worst = cols[0]
        text = (
            f"{len(cols)} of {fmt(profile['columns'])} columns contain missing values: {fmt(profile['missing_cells'])} "
            f"of {fmt(profile['total_cells'])} cells ({profile['missing_pct']}%). “{worst['name']}” has the most: "
            f"{fmt(worst['missing'])} of {fmt(worst['rows'])} rows ({worst['missing_pct']}%)."
        )
    return _answer(
        "missing_summary",
        p,
        text,
        table=_table(
            ["Column", "Missing rows", "Missing %"], [[c["name"], c["missing"], f"{c['missing_pct']}%"] for c in cols]
        ),
    )


def _duplicate_summary(p: DuplicateSummary, tf: TypedFrame, profile: dict[str, Any], *_: Any) -> dict[str, Any]:
    if not p.key_columns:
        n = profile["duplicate_rows"]
        text = (
            f"{fmt(n)} of {fmt(profile['rows'])} rows are exact copies of an earlier row."
            if n
            else f"No row is an exact copy of another among the {fmt(profile['rows'])} rows."
        )
        return _answer("duplicate_summary", p, text)
    df = tf.df[p.key_columns]
    has_key = df.notna().any(axis=1)
    dup = df.duplicated(keep="first") & has_key
    groups = int(df[df.duplicated(keep=False) & has_key].drop_duplicates().shape[0])
    names = ", ".join(f"“{c}”" for c in p.key_columns)
    n = int(dup.sum())
    text = (
        f"{fmt(n)} rows repeat an earlier combination of {names}, across {fmt(groups)} repeated combinations."
        if n
        else f"Every combination of {names} appears once."
    )
    return _answer("duplicate_summary", p, text)


def _column_profile(p: ColumnProfile, tf: TypedFrame, profile: dict[str, Any], *_: Any) -> dict[str, Any]:
    c = next(x for x in profile["column_profiles"] if x["name"] == p.column)
    text = (
        f"“{p.column}” is a {c['type']} column with {fmt(c['non_missing'])} filled and {fmt(c['missing'])} missing "
        f"values out of {fmt(c['rows'])} rows, and {fmt(c['unique'])} distinct values."
    )
    rows: list[list[Any]] = [
        ["Type", c["type"]],
        ["Filled", c["non_missing"]],
        ["Missing", c["missing"]],
        ["Distinct values", c["unique"]],
    ]
    if c.get("numeric"):
        m = c["numeric"]
        text += f" Values run from {fmt(m['min'])} to {fmt(m['max'])}, with a median of {fmt(m['median'])} and an average of {fmt(m['mean'])}."
        rows += [["Minimum", m["min"]], ["Maximum", m["max"]], ["Median", m["median"]], ["Average", m["mean"]]]
    elif c.get("date"):
        d = c["date"]
        if d["min"]:
            text += f" Clear dates run from {d['min'][:10]} to {d['max'][:10]}."
            rows += [["Earliest", d["min"][:10]], ["Latest", d["max"][:10]]]
        if d["ambiguous"] or d["invalid"]:
            text += f" {fmt(d['ambiguous'])} dates are ambiguous and {fmt(d['invalid'])} are impossible."
    elif c.get("top_values"):
        top = c["top_values"][0]
        text += f" The most frequent value is “{top['value']}” ({fmt(top['count'])} rows)."
        rows += [[f"“{t['value']}”", t["count"]] for t in c["top_values"][:5]]
    if c.get("mixed"):
        text += " The column mixes several kinds of values."
    return _answer("column_profile", p, text, table=_table(["Property", "Value"], rows))


def _outlier_summary(p: OutlierSummary, tf: TypedFrame, *_: Any) -> dict[str, Any]:
    c = tf.col(p.column)
    if c.kind != "number":
        raise AppError(422, "NOT_NUMERIC", f"“{p.column}” is not numeric, so unusual values cannot be measured.")
    v = c.numbers[~np.isnan(c.numbers)]
    if len(v) < 20:
        return _answer(
            "outlier_summary",
            p,
            f"“{p.column}” has only {fmt(len(v))} numeric values; at least 20 are needed to judge what is unusual.",
        )
    q1, q3 = np.quantile(v, [0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        return _answer(
            "outlier_summary", p, f"Most values in “{p.column}” are identical, so an unusual range cannot be defined."
        )
    lo, hi = q1 - 3 * iqr, q3 + 3 * iqr
    below, above = int((v < lo).sum()), int((v > hi).sum())
    if below + above == 0:
        text = f"No value in “{p.column}” lies outside the typical range of {fmt(float(lo))} to {fmt(float(hi))}."
    else:
        text = (
            f"{fmt(below + above)} of {fmt(len(v))} values in “{p.column}” lie outside the typical range of {fmt(float(lo))} to "
            f"{fmt(float(hi))}: {fmt(below)} below and {fmt(above)} above. The smallest value is {fmt(float(v.min()))} and the "
            f"largest is {fmt(float(v.max()))}. They may be errors or genuine; that needs your judgement."
        )
    text += " The typical range is the middle half of the values, widened by three times its width on each side."
    return _answer("outlier_summary", p, text)


def _chart_suggestions(p: NoParams, tf: TypedFrame, profile: dict[str, Any], sensitive: list[str]) -> dict[str, Any]:
    rec = recommend(tf, sensitive)
    charts = rec["charts"]
    text = (
        f"{len(charts)} charts fit this data, chosen from the column types only."
        if charts
        else "No chart can be suggested from the column types of this data."
    )
    if rec["notes"]:
        text += " " + " ".join(rec["notes"])
    return _answer(
        "chart_suggestions",
        p,
        text,
        table=_table(["Chart", "Type", "Why"], [[w["title"], w["chart"], w["reason"]] for w in charts]),
    )


def _quality_explain(p: QualityExplain, tf: TypedFrame, profile: dict[str, Any], *_: Any) -> dict[str, Any]:
    health = profile["health"]
    issues = [i for i in profile["issues"] if not p.codes or i["code"] in p.codes]
    parts = ", ".join(f"{c['key']} {fmt(c['points'])} of {fmt(100 * c['weight'])} points" for c in health["components"])
    text = f"The Data Health Score is {health['score']} out of 100 ({health['band']}). It is made of: {parts}."
    if issues:
        top = issues[:3]
        text += (
            f" {len(issues)} issues were found. The most important: "
            + "; ".join(
                f"{i['title']}" + (f" in “{i['column']}”" if i["column"] else "") + f" ({fmt(i['affected_rows'])} rows)"
                for i in top
            )
            + "."
        )
    else:
        text += " No issues were found." if not p.codes else " No issue of that kind was found."
    return _answer(
        "quality_explain",
        p,
        text,
        table=_table(
            ["Issue", "Column", "Rows", "Severity", "Suggested fix"],
            [
                [
                    i["title"],
                    i["column"] or "(whole sheet)",
                    i["affected_rows"],
                    i["severity"],
                    i["suggested_action"]["label"] or "Review manually",
                ]
                for i in issues
            ],
        ),
    )


_RUN = {
    "count_rows": _count_rows,
    "aggregate": _aggregate,
    "group_rank": _group_rank,
    "time_trend": _time_trend,
    "extreme_period": _extreme_period,
    "compare_groups": _compare_groups,
    "distribution": _distribution,
    "correlation": _correlation,
    "missing_summary": _missing_summary,
    "duplicate_summary": _duplicate_summary,
    "column_profile": _column_profile,
    "outlier_summary": _outlier_summary,
    "chart_suggestions": _chart_suggestions,
    "quality_explain": _quality_explain,
}
