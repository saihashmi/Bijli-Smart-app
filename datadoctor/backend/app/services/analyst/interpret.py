"""Local, rule-based question interpreter (SPEC FR-5.3). No network, no model.

It maps common phrasings to one allowlisted operation with parameters. It only picks a column when the question
names it or when there is exactly one candidate; otherwise it says what it could not work out rather than guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..analytics.typed import TypedFrame

GRAINS = {
    "day": r"\b(daily|per day|by day|each day|day)\b",
    "week": r"\b(weekly|per week|by week|each week|week)\b",
    "month": r"\b(monthly|per month|by month|each month|month)\b",
    "quarter": r"\b(quarterly|per quarter|by quarter|quarter)\b",
    "year": r"\b(yearly|annual|annually|per year|by year|each year|year)\b",
}
AGGS = [
    ("median", r"\bmedian\b"),
    ("avg", r"\b(average|mean|avg|typical)\b"),
    ("sum", r"\b(total|sum|overall|altogether|combined)\b"),
    ("distinct", r"\b(distinct|unique|different)\b"),
    ("max", r"\b(maximum|max|largest value|biggest value|highest value)\b"),
    ("min", r"\b(minimum|min|smallest value|lowest value)\b"),
    ("count", r"\b(how many|count|number of)\b"),
]
HIGH = r"\b(highest|most|top|largest|biggest|best|greatest|maximum|max)\b"
LOW = r"\b(lowest|least|fewest|smallest|worst|bottom|minimum|min)\b"


@dataclass
class Interpretation:
    operation: str | None
    params: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None  # why nothing was chosen
    alternatives: list[str] = field(default_factory=list)


def _mentioned(question: str, names: list[str]) -> list[str]:
    """Column names (or values) that appear in the question as whole words, longest first, in order of appearance."""
    q = question.casefold()
    hits: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for name in sorted(names, key=len, reverse=True):
        key = name.strip().casefold()
        if len(key) < 2:
            continue
        for m in re.finditer(rf"(?<![\w]){re.escape(key)}(?![\w])", q):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            hits.append((m.start(), -len(key), name))
            break
    return [name for _, _, name in sorted(hits)]


def _agg(q: str) -> str | None:
    for agg, pattern in AGGS:
        if re.search(pattern, q):
            return agg
    return None


def _grain(q: str) -> str | None:
    for grain, pattern in GRAINS.items():
        if re.search(pattern, q):
            return grain
    return None


def interpret(question: str, tf: TypedFrame, sensitive: list[str] | None = None) -> Interpretation:
    q = " ".join(question.casefold().split())
    kinds = {name: tf.col(name).kind for name in tf.columns}
    named = _mentioned(question, tf.columns)
    numeric = [n for n in tf.columns if kinds[n] == "number"]
    dates = [n for n in tf.columns if kinds[n] == "date"]
    groupable = [
        n
        for n in tf.columns
        if kinds[n] in ("category", "boolean") or (kinds[n] in ("text", "number") and tf.col(n).unique <= 50)
    ]
    named_numeric = [n for n in named if kinds[n] == "number"]
    named_dates = [n for n in named if kinds[n] == "date"]
    agg = _agg(q)
    # A number column counts as a group only when no calculation is asked of numbers ("rows by Year").
    named_groups = [n for n in named if n in groupable and kinds[n] != "date" and not (kinds[n] == "number" and agg)]
    grain = _grain(q)

    def one(named_list: list[str], all_list: list[str]) -> str | None:
        if named_list:
            return named_list[0]
        return all_list[0] if len(all_list) == 1 else None

    def measure_params() -> dict[str, Any] | None:
        """measure + agg from the question. None when a calculation was asked for but the column is unclear."""
        if agg in (None, "count") and not named_numeric:
            return {"agg": "count"}
        m = one(named_numeric, numeric)
        if m is None:
            return None
        return {"measure": m, "agg": agg if agg and agg != "count" else "sum"}

    def unclear(what: str, options: list[str]) -> Interpretation:
        shown = ", ".join(f"“{o}”" for o in options[:6]) or "none in this data"
        return Interpretation(
            None,
            reason=f"I could not tell which {what} you mean. Candidates: {shown}. Name the column in your question, or use the guided builder.",
        )

    if re.search(r"\b(missing|empty|blank|null|incomplete|gaps?)\b", q):
        return Interpretation("missing_summary")
    if re.search(r"\bduplicat", q):
        keys = [n for n in named]
        return Interpretation(
            "duplicate_summary", {"key_columns": keys} if keys and re.search(r"\b(by|on|same|key)\b", q) else {}
        )
    if re.search(r"\b(score|quality|health|issues?|problems?|wrong with)\b", q):
        return Interpretation("quality_explain")
    if re.search(r"\b(charts?|graphs?|visuali[sz]|plots?)\b", q) and re.search(
        r"\b(suggest|recommend|best|which|what)\b", q
    ):
        return Interpretation("chart_suggestions")
    if re.search(r"\b(outliers?|anomal\w*|unusual|extreme values|strange)\b", q):
        col = one(named_numeric, numeric)
        return Interpretation("outlier_summary", {"column": col}) if col else unclear("numeric column", numeric)
    if re.search(r"\b(correlat|related|relationship|associated|depend)", q):
        if len(named_numeric) >= 2:
            return Interpretation("correlation", {"x": named_numeric[0], "y": named_numeric[1]})
        if len(numeric) == 2 and not named_numeric:
            return Interpretation("correlation", {"x": numeric[0], "y": numeric[1]})
        return unclear("two numeric columns", numeric)
    if re.search(r"\b(distribut\w*|spread|histogram|range of)\b", q):
        col = one(named_numeric, numeric)
        return Interpretation("distribution", {"column": col}) if col else unclear("numeric column", numeric)
    if re.search(r"\b(describe|profile|summari[sz]e|tell me about|what is in)\b", q) and named:
        return Interpretation("column_profile", {"column": named[0]})

    # compare two or more named values of one category column
    if re.search(r"\b(compare|versus|vs\.?|difference between)\b", q):
        for g in [
            *named_groups,
            *sorted((n for n in groupable if n not in named_groups), key=lambda n: kinds[n] == "number"),
        ]:
            values = _mentioned(question, tf.col(g).labels)
            if len(values) >= 2:
                mp = measure_params()
                if mp is None:
                    return unclear("numeric column", numeric)
                return Interpretation("compare_groups", {"group_by": g, "values": values[:5], **mp})
        if named_groups:
            mp = measure_params() or {"agg": "count"}
            return Interpretation("group_rank", {"group_by": named_groups[0], **mp})
        return Interpretation(
            None,
            reason="To compare groups, name two values that appear in one column, for example “compare Lahore and Karachi”.",
        )

    # periods
    date_col = one(named_dates, dates)
    asks_period = grain and re.search(r"\b(which|what)\b", q) and (re.search(HIGH, q) or re.search(LOW, q))
    if asks_period:
        if not date_col:
            return (
                unclear("date column", dates)
                if dates
                else Interpretation(None, reason="This data has no date column, so periods cannot be compared.")
            )
        mp = measure_params()
        if mp is None:
            return unclear("numeric column", numeric)
        return Interpretation(
            "extreme_period",
            {"date_col": date_col, "grain": grain, "which": "min" if re.search(LOW, q) else "max", **mp},
        )
    if re.search(r"\b(trend|over time|time series|timeline|growth|change over)\b", q) or (
        grain and re.search(r"\b(per|by|each)\b|ly\b", q)
    ):
        if not date_col:
            return (
                unclear("date column", dates)
                if dates
                else Interpretation(None, reason="This data has no date column, so a trend over time cannot be shown.")
            )
        mp = measure_params()
        if mp is None:
            return unclear("numeric column", numeric)
        return Interpretation("time_trend", {"date_col": date_col, "grain": grain or "month", **mp})

    # ranking by a category
    ranking = re.search(HIGH, q) or re.search(LOW, q) or re.search(r"\b(by|per|each|every|breakdown|split|rank)\b", q)
    if named_groups and ranking:
        mp = measure_params()
        if mp is None:
            return unclear("numeric column", numeric)
        return Interpretation(
            "group_rank",
            {
                "group_by": named_groups[0],
                "order": "asc" if re.search(LOW, q) and not re.search(HIGH, q) else "desc",
                **mp,
            },
        )

    # single figures
    if named_numeric and agg:
        return Interpretation("aggregate", {"measure": named_numeric[0], "agg": agg if agg != "count" else "count"})
    if agg and agg != "count" and not named:
        col = one([], numeric)
        return Interpretation("aggregate", {"measure": col, "agg": agg}) if col else unclear("numeric column", numeric)
    if re.search(r"\b(how many|count|number of)\b", q) and re.search(
        r"\b(rows?|records?|entries|lines|items|there)\b", q
    ):
        return Interpretation("count_rows")
    if named and len(named) == 1:
        return Interpretation("column_profile", {"column": named[0]})

    return Interpretation(
        None,
        reason="I can't answer that with this data or the supported operations.",
    )
