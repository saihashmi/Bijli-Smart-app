"""Field catalogue and deterministic chart recommendations (SPEC §12.4).

Recommendations look only at column types and counts. Column names are never used to guess a business meaning:
the reason says "Amount is numeric", never "Amount is revenue".
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .query import AGG_LABEL, AGGS_BY_KIND
from .typed import TypedFrame

LOW_CARDINALITY = 12
DONUT_MAX = 6
MAX_WIDGETS = 6


def fields(tf: TypedFrame, sensitive: list[str] | None = None) -> list[dict[str, Any]]:
    out = []
    hidden = set(sensitive or [])
    for name in tf.columns:
        c = tf.col(name)
        present = c.n - int(c.missing.sum())
        info: dict[str, Any] = {
            "name": name,
            "kind": c.kind,
            "unique": c.unique,
            "present": present,
            "missing": c.n - present,
            "aggregations": AGGS_BY_KIND[c.kind],
            "can_group": c.kind in ("category", "boolean", "date") or (c.kind in ("number", "text") and c.unique <= 50),
            "can_measure": c.kind == "number",
            "sensitive": name in hidden,
        }
        if c.kind == "number":
            v = c.numbers[~np.isnan(c.numbers)]
            info["min"], info["max"] = (float(v.min()), float(v.max())) if len(v) else (None, None)
            info["not_usable"] = c.not_numeric
        elif c.kind == "date":
            d = c.dates[~np.isnat(c.dates)]
            info["min"], info["max"] = (str(d.min())[:10], str(d.max())[:10]) if len(d) else (None, None)
            info["not_usable"] = c.not_dated
        elif c.kind in ("category", "boolean") or c.unique <= 50:
            order = np.argsort(-np.bincount(c.codes[c.codes >= 0], minlength=len(c.labels)), kind="stable")
            info["values"] = [c.labels[i] for i in order[:50]]
        out.append(info)
    return out


def _widget(wid: str, title: str, chart: str, query: dict[str, Any], reason: str, width: int = 6) -> dict[str, Any]:
    return {"id": wid, "title": title, "chart": chart, "query": query, "reason": reason, "width": width}


def recommend(tf: TypedFrame, sensitive: list[str] | None = None) -> dict[str, Any]:
    """Up to four KPI cards and six charts, each with the reason it was chosen."""
    hidden = set(sensitive or [])
    cols = [tf.col(n) for n in tf.columns if n not in hidden]
    # Measures with more distinct values first: a column with a handful of repeated numbers (a price list, a
    # rating) is a weaker candidate for totals than one that varies row by row. Ties keep sheet order.
    numeric = sorted(
        (c for c in cols if c.kind == "number" and c.unique > 1 and not _looks_like_id(c)), key=lambda c: -c.unique
    )
    dates = [c for c in cols if c.kind == "date" and int((~np.isnat(c.dates)).sum()) >= 2]
    cats = [c for c in cols if c.kind in ("category", "boolean") and 2 <= c.unique <= LOW_CARDINALITY]

    kpis = [
        _widget(
            "kpi-rows",
            "Rows",
            "kpi",
            {"kind": "aggregate", "measure": {"agg": "count"}},
            "Every dataset has a row count.",
            3,
        )
    ]
    for agg, c in (
        [("sum", m) for m in numeric[:1]] + [("avg", m) for m in numeric[:1]] + [("sum", m) for m in numeric[1:2]]
    ):
        kpis.append(
            _widget(
                f"kpi-{agg}-{len(kpis)}",
                f"{AGG_LABEL[agg]} of {c.name}",
                "kpi",
                {"kind": "aggregate", "measure": {"agg": agg, "column": c.name}},
                f"“{c.name}” is numeric with {c.unique} distinct values, so its {AGG_LABEL[agg].lower()} "
                "can be calculated.",
                3,
            )
        )

    charts: list[dict[str, Any]] = []

    def add(w: dict[str, Any]) -> None:
        if len(charts) < MAX_WIDGETS:
            charts.append(w)

    if dates and numeric:
        d, m = dates[0], numeric[0]
        usable = d.dates[~np.isnat(d.dates)]
        span = int((usable.max() - usable.min()) / np.timedelta64(1, "D"))
        grain = "day" if span < 62 else "month"
        add(
            _widget(
                "line-1",
                f"{AGG_LABEL['sum']} of {m.name} by {grain}",
                "line",
                {
                    "kind": "aggregate",
                    "measure": {"agg": "sum", "column": m.name},
                    "dimension": {"column": d.name, "grain": grain},
                },
                f"“{d.name}” holds dates and “{m.name}” is numeric. The dates span {span} days, so values are "
                f"totalled per {grain}.",
                12,
            )
        )

    def bar_sum(c: Any) -> None:
        if not numeric:
            return
        m = numeric[0]
        add(
            _widget(
                f"bar-{c.name}",
                f"Sum of {m.name} by {c.name}",
                "bar",
                {
                    "kind": "aggregate",
                    "measure": {"agg": "sum", "column": m.name},
                    "dimension": {"column": c.name},
                    "sort": {"by": "value", "dir": "desc"},
                    "limit": 10,
                },
                f"“{c.name}” has {c.unique} distinct values and “{m.name}” is numeric: a bar per value, largest first.",
            )
        )

    def count_chart(c: Any) -> None:
        chart = "donut" if c.unique <= DONUT_MAX else "bar"
        add(
            _widget(
                f"count-{c.name}",
                f"Rows by {c.name}",
                chart,
                {
                    "kind": "aggregate",
                    "measure": {"agg": "count"},
                    "dimension": {"column": c.name},
                    "sort": {"by": "value", "dir": "desc"},
                    "limit": 10,
                },
                f"“{c.name}” has {c.unique} distinct values"
                + (", few enough to compare as shares of the whole." if chart == "donut" else ": a bar per value."),
            )
        )

    # Variety first: one chart of each kind the columns support, then second helpings.
    if cats:
        bar_sum(cats[0])
        count_chart(cats[1] if len(cats) > 1 else cats[0])
    if numeric:
        m = numeric[0]
        add(
            _widget(
                "hist-1",
                f"Distribution of {m.name}",
                "histogram",
                {"kind": "histogram", "column": m.name, "bins": 20},
                f"“{m.name}” is numeric: a histogram shows how its values are spread.",
            )
        )
    if len(numeric) >= 2:
        a, b = numeric[1], numeric[0]
        add(
            _widget(
                "scatter-1",
                f"{b.name} against {a.name}",
                "scatter",
                {"kind": "scatter", "x": a.name, "y": b.name},
                f"“{a.name}” and “{b.name}” are both numeric. Up to 2,000 points are shown; larger data is sampled "
                "and the sample is disclosed.",
            )
        )
    if len(cats) > 1:
        bar_sum(cats[1])
        count_chart(cats[0])

    halves = [w for w in charts if w["width"] == 6]
    if len(halves) % 2:
        halves[-1]["width"] = 12  # no half-empty last row

    notes = []
    if not numeric:
        notes.append(
            "No numeric column was found, so totals, averages, histograms and scatter plots are not suggested."
        )
    if not dates:
        notes.append("No usable date column was found, so no chart over time is suggested.")
    if not cats:
        notes.append(
            f"No column with 2 to {LOW_CARDINALITY} distinct values was found, so no category chart is suggested."
        )
    if hidden:
        notes.append("Columns marked as sensitive are left out of suggestions.")
    return {"kpis": kpis, "charts": charts, "notes": notes}


def _looks_like_id(c: Any) -> bool:
    """A whole-number column where every value is different is almost certainly an identifier, not a measure."""
    v = c.numbers[~np.isnan(c.numbers)]
    return (
        len(v) >= 20
        and c.unique == len(v)
        and bool(np.all(np.mod(v, 1) == 0))
        and bool(np.all(np.diff(np.sort(v)) == 1))
    )
