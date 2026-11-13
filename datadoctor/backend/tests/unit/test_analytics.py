"""M9: the analytics engine. Every figure is compared with an independent pandas calculation on clean columns."""

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
from pydantic import TypeAdapter

from app.errors import AppError
from app.services.analytics import query as aq
from app.services.analytics.recommend import fields, recommend
from app.services.analytics.typed import TypedFrame

Q = TypeAdapter(aq.Query)
N = 600


def q(**kw):
    return Q.validate_python({"kind": "aggregate", **kw})


@pytest.fixture(scope="module")
def data():
    """A clean reference frame (truth) and the messy raw frame the engine sees."""
    rng = np.random.default_rng(7)
    truth = pd.DataFrame(
        {
            "City": rng.choice(["Lahore", "Karachi", "Islamabad", "Quetta"], N, p=[0.4, 0.3, 0.2, 0.1]),
            "Channel": rng.choice(["Web", "Shop"], N),
            "Amount": np.round(rng.gamma(2.0, 500.0, N), 2),
            "Units": rng.integers(1, 40, N).astype(float),
            "When": pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 500, N), unit="D"),
        }
    )
    raw = truth.astype(object).copy()
    raw["When"] = pd.Series([datetime(t.year, t.month, t.day) for t in truth["When"]], dtype=object)
    # Messy cells. The truth frame gets NaN/NaT in the same places: what the engine must leave out.
    for i in range(0, N, 25):  # missing amounts, in three different spellings
        raw.at[i, "Amount"] = [None, "N/A", "  "][(i // 25) % 3]
        truth.at[i, "Amount"] = np.nan
    for i in range(3, N, 40):  # amounts stored as formatted text: still numbers
        raw.at[i, "Amount"] = f"Rs {truth.at[i, 'Amount']:,.2f}"
    truth["AmountCell"] = truth["Amount"].astype(object)  # for count/distinct: any non-empty cell counts
    for i in range(7, N, 60):  # text that is not a number: left out of the maths, never zero
        raw.at[i, "Amount"] = "pending"
        truth.at[i, "Amount"] = np.nan
        truth.at[i, "AmountCell"] = "pending"
    for i in range(11, N, 50):  # ambiguous dates: in no period
        raw.at[i, "When"] = "03/04/2025"
        truth.at[i, "When"] = pd.NaT
    for i in range(13, N, 70):  # impossible dates
        raw.at[i, "When"] = "31/02/2025"
        truth.at[i, "When"] = pd.NaT
    for i in range(17, N, 45):  # missing city
        raw.at[i, "City"] = None
        truth.at[i, "City"] = None
    return truth, TypedFrame(raw)


AGGS = {
    "sum": lambda s: s.sum(min_count=1),
    "avg": lambda s: s.mean(),
    "min": lambda s: s.min(),
    "max": lambda s: s.max(),
    "median": lambda s: s.median(),
    "count": lambda s: s.count(),
    "distinct": lambda s: s.nunique(),
}


@pytest.mark.parametrize("agg", list(AGGS))
def test_kpi_matches_pandas(data, agg):
    truth, tf = data
    res = aq.run(tf, q(measure={"agg": agg, "column": "Amount"}))
    column = "AmountCell" if agg in ("count", "distinct") else "Amount"
    assert res["total"]["value"] == pytest.approx(float(AGGS[agg](truth[column])))
    assert res["meta"]["rows_total"] == N


def test_row_count_and_measure_meta(data):
    truth, tf = data
    assert aq.run(tf, q())["total"] == {"value": N, "n": N}
    meta = aq.run(tf, q(measure={"agg": "sum", "column": "Amount"}))["meta"]
    assert meta["measure_missing"] == len(range(0, N, 25))
    assert meta["measure_not_usable"] == len(range(7, N, 60))
    assert meta["measure_missing"] + meta["measure_not_usable"] == int(truth["Amount"].isna().sum())


@pytest.mark.parametrize("agg", list(AGGS))
def test_group_by_category_matches_pandas(data, agg):
    truth, tf = data
    res = aq.run(tf, q(measure={"agg": agg, "column": "Amount"}, dimension={"column": "City"}))
    column = "AmountCell" if agg in ("count", "distinct") else "Amount"
    expected = truth.groupby("City", dropna=False)[column].apply(AGGS[agg])
    got = {r["label"]: r["value"] for r in res["rows"]}
    assert set(got) == {"Lahore", "Karachi", "Islamabad", "Quetta", "(missing)"}
    for label, value in expected.items():
        key = "(missing)" if pd.isna(label) else label
        assert got[key] == pytest.approx(float(value)), (agg, key)
    assert res["meta"]["dimension_missing"] == int(truth["City"].isna().sum())
    assert sum(r["rows"] for r in res["rows"]) == N  # every row is in exactly one group
    values = [r["value"] for r in res["rows"]]
    assert values == sorted(values, reverse=True)  # default: largest first


@pytest.mark.parametrize(
    "grain,freq", [("day", "D"), ("week", "W-SUN"), ("month", "M"), ("quarter", "Q"), ("year", "Y")]
)
def test_time_series_matches_pandas(data, grain, freq):
    truth, tf = data
    res = aq.run(tf, q(measure={"agg": "sum", "column": "Amount"}, dimension={"column": "When", "grain": grain}))
    dated = truth.dropna(subset=["When"])
    expected = dated.groupby(dated["When"].dt.to_period(freq))["Amount"].apply(lambda s: s.sum(min_count=1))
    assert len(res["rows"]) == len(expected)
    for row, (period, value) in zip(res["rows"], expected.items(), strict=True):
        assert row["key"] == str(period.start_time.date())
        if pd.isna(value):
            assert row["value"] is None  # a period with no usable amounts is null, not 0
        else:
            assert row["value"] == pytest.approx(float(value))
    assert [r["key"] for r in res["rows"]] == sorted(r["key"] for r in res["rows"])  # chronological
    not_dated = len(set(range(11, N, 50)) | set(range(13, N, 70)))
    assert res["meta"]["dimension_not_dated"] == not_dated  # ambiguous + impossible dates are in no period
    assert sum(r["rows"] for r in res["rows"]) == N - not_dated


def test_series_split_matches_pandas(data):
    truth, tf = data
    res = aq.run(tf, q(measure={"agg": "avg", "column": "Units"}, dimension={"column": "City"}, series="Channel"))
    assert sorted(res["series"]["names"]) == ["Shop", "Web"]
    for row in res["rows"]:
        in_city = truth["City"].isna() if row["missing"] else truth["City"] == row["label"]
        for name, value in row["values"].items():
            assert value == pytest.approx(float(truth.loc[in_city & (truth["Channel"] == name), "Units"].mean()))


def test_filters_match_pandas(data):
    truth, tf = data
    filters = [
        {"op": "in", "column": "City", "values": ["Lahore", "Karachi"]},
        {"op": "range", "column": "Units", "min": 5, "max": 30},
        {"op": "date_range", "column": "When", "start": "2025-03-01", "end": "2025-12-31"},
    ]
    res = aq.run(tf, q(measure={"agg": "sum", "column": "Amount"}, filters=filters))
    keep = (
        truth["City"].isin(["Lahore", "Karachi"])
        & truth["Units"].between(5, 30)
        & (truth["When"] >= "2025-03-01")
        & (truth["When"] < "2026-01-01")  # the end date is inclusive
    )
    assert res["meta"]["rows_after_filters"] == int(keep.sum())
    assert res["total"]["value"] == pytest.approx(float(truth.loc[keep, "Amount"].sum()))
    assert [f["rows_matching"] for f in res["meta"]["filters"]] == [
        int(truth["City"].isin(["Lahore", "Karachi"]).sum()),
        int(truth["Units"].between(5, 30).sum()),
        int(((truth["When"] >= "2025-03-01") & (truth["When"] < "2026-01-01")).sum()),
    ]

    excluded = aq.run(
        tf, q(filters=[{"op": "not_in", "column": "City", "values": ["Lahore"], "include_missing": True}])
    )
    assert excluded["total"]["value"] == int((truth["City"].notna() & (truth["City"] != "Lahore")).sum())
    typo = aq.run(tf, q(filters=[{"op": "in", "column": "City", "values": ["Lahor"]}]))
    assert typo["total"]["value"] == 0 and typo["meta"]["filters"][0]["values_not_in_data"] == ["Lahor"]


def test_top_n_with_other_is_recomputed_not_summed(data):
    truth, tf = data
    res = aq.run(tf, q(measure={"agg": "median", "column": "Amount"}, dimension={"column": "City"}, limit=3))
    assert len(res["rows"]) == 3 and res["rows"][-1]["other"] is True
    assert res["meta"]["other_groups"] == 3 and res["meta"]["groups_total"] == 5
    shown = [r["label"] for r in res["rows"][:2]]
    city = truth["City"].fillna("(missing)")
    rest = truth.loc[~city.isin(shown), "Amount"]
    assert res["rows"][-1]["value"] == pytest.approx(float(rest.median()))  # the true median of the remaining rows
    dropped = aq.run(
        tf, q(measure={"agg": "sum", "column": "Amount"}, dimension={"column": "City"}, limit=2, other=False)
    )
    assert len(dropped["rows"]) == 2 and dropped["meta"]["other_included"] is False


def test_sorting(data):
    _, tf = data
    by_label = aq.run(tf, q(dimension={"column": "City"}, sort={"by": "label", "dir": "asc"}))
    assert [r["label"] for r in by_label["rows"]] == ["Islamabad", "Karachi", "Lahore", "Quetta", "(missing)"]
    asc = aq.run(tf, q(dimension={"column": "City"}, sort={"by": "value", "dir": "asc"}))
    assert [r["value"] for r in asc["rows"]] == sorted(r["value"] for r in asc["rows"])
    numeric = aq.run(tf, q(dimension={"column": "Units"}, sort={"by": "label", "dir": "asc"}))
    assert [float(r["label"]) for r in numeric["rows"]] == sorted(
        float(r["label"]) for r in numeric["rows"]
    )  # 2 before 10


def test_point_cap_groups_the_rest(data):
    frame = pd.DataFrame({"Id": [f"k{i}" for i in range(1200)], "V": [1.0] * 1200}).astype(object)
    res = aq.run(TypedFrame(frame), q(measure={"agg": "sum", "column": "V"}, dimension={"column": "Id"}))
    assert len(res["rows"]) == aq.MAX_POINTS and res["meta"]["capped"] is True
    assert res["rows"][-1]["other"] is True and res["rows"][-1]["value"] == 1200 - (aq.MAX_POINTS - 1)
    assert sum(r["value"] for r in res["rows"]) == 1200  # nothing lost


def test_histogram_matches_numpy(data):
    truth, tf = data
    res = aq.run(tf, Q.validate_python({"kind": "histogram", "column": "Amount", "bins": 12}))
    values = truth["Amount"].dropna().to_numpy()
    counts, edges = np.histogram(values, bins=12)
    assert [b["count"] for b in res["bins"]] == counts.tolist()
    assert res["bins"][0]["start"] == pytest.approx(edges[0]) and res["bins"][-1]["end"] == pytest.approx(edges[-1])
    assert res["meta"]["values_used"] == len(values) and sum(counts) == len(values)
    assert res["stats"]["median"] == pytest.approx(float(np.median(values)))


def test_scatter_and_correlation(data):
    truth, tf = data
    res = aq.run(tf, Q.validate_python({"kind": "scatter", "x": "Units", "y": "Amount"}))
    pairs = truth[["Units", "Amount"]].dropna()
    assert res["meta"]["pairs_used"] == len(pairs) and res["meta"]["sampled"] is False
    assert res["meta"]["pairs_left_out"] == N - len(pairs)
    assert res["pearson_r"] == pytest.approx(float(pairs["Units"].corr(pairs["Amount"])))

    rng = np.random.default_rng(1)
    x = rng.normal(size=5000)
    big = pd.DataFrame({"x": x, "y": x * 2 + rng.normal(size=5000)}).astype(object)
    sampled = aq.run(TypedFrame(big), Q.validate_python({"kind": "scatter", "x": "x", "y": "y"}))
    assert sampled["meta"] | {"filters": []} == sampled["meta"]
    assert sampled["meta"]["sampled"] is True and len(sampled["points"]) == aq.SCATTER_SAMPLE
    assert sampled["pearson_r"] == pytest.approx(
        float(np.corrcoef(big["x"].astype(float), big["y"].astype(float))[0, 1])
    )
    again = aq.run(TypedFrame(big), Q.validate_python({"kind": "scatter", "x": "x", "y": "y"}))
    assert again["points"] == sampled["points"]  # the sample is repeatable


def test_table_query(data):
    truth, tf = data
    res = aq.run(
        tf,
        Q.validate_python(
            {
                "kind": "table",
                "columns": ["City", "Units"],
                "filters": [{"op": "in", "column": "City", "values": ["Quetta"]}],
                "limit": 5,
            }
        ),
        header_row=1,
    )
    idx = truth.index[truth["City"] == "Quetta"]
    assert res["total"] == len(idx) and len(res["rows"]) == 5
    assert res["row_numbers"] == [int(i) + 3 for i in idx[:5]]
    assert all(r[0] == "Quetta" for r in res["rows"])


@pytest.mark.parametrize(
    "spec,code",
    [
        ({"measure": {"agg": "sum", "column": "City"}}, "AGGREGATION_NOT_ALLOWED"),
        ({"measure": {"agg": "avg", "column": "When"}}, "AGGREGATION_NOT_ALLOWED"),
        ({"measure": {"agg": "sum"}}, "MEASURE_NEEDS_COLUMN"),
        ({"measure": {"agg": "sum", "column": "Nope"}}, "UNKNOWN_COLUMN"),
        ({"dimension": {"column": "When"}}, "GRAIN_REQUIRED"),
        ({"dimension": {"column": "City", "grain": "month"}}, "GRAIN_NOT_ALLOWED"),
        ({"series": "Channel"}, "SERIES_NEEDS_DIMENSION"),
        ({"dimension": {"column": "City"}, "series": "City"}, "SERIES_SAME_AS_DIMENSION"),
        ({"filters": [{"op": "range", "column": "City", "min": 1}]}, "FILTER_NOT_NUMERIC"),
        ({"filters": [{"op": "date_range", "column": "Amount", "start": "2025-01-01"}]}, "FILTER_NOT_DATE"),
    ],
)
def test_invalid_combinations_are_refused(data, spec, code):
    _, tf = data
    with pytest.raises(AppError) as e:
        aq.run(tf, q(**spec))
    assert e.value.code == code and e.value.status == 422


def test_date_min_max_and_empty_groups(data):
    truth, tf = data
    res = aq.run(tf, q(measure={"agg": "max", "column": "When"}))
    assert res["total"]["value"] == str(truth["When"].max().date())
    frame = pd.DataFrame({"G": ["a", "a", "b"], "V": [1.0, 2.0, "n/a"]}).astype(object)
    empty = aq.run(TypedFrame(frame), q(measure={"agg": "sum", "column": "V"}, dimension={"column": "G"}))
    assert {r["label"]: r["value"] for r in empty["rows"]} == {"a": 3, "b": None}  # never 0 for "no values"
    assert empty["rows"][-1]["label"] == "b"  # groups without a value sort last


def test_fields_and_recommendations(data):
    _, tf = data
    info = {f["name"]: f for f in fields(tf, sensitive=["Channel"])}
    assert (
        info["Amount"]["kind"] == "number" and "sum" in info["Amount"]["aggregations"] and info["Amount"]["can_measure"]
    )
    assert info["City"]["kind"] == "category" and info["City"]["aggregations"] == ["count", "distinct"]
    assert info["City"]["values"][0] == "Lahore"  # most frequent first
    assert info["When"]["kind"] == "date" and info["When"]["min"] <= info["When"]["max"]
    assert info["When"]["not_usable"] == len(set(range(11, N, 50)) | set(range(13, N, 70)))
    assert info["Channel"]["sensitive"] is True

    rec = recommend(tf, sensitive=["Channel"])
    assert rec["kpis"][0]["query"] == {"kind": "aggregate", "measure": {"agg": "count"}}
    charts = {w["chart"] for w in rec["charts"]}
    assert {"line", "bar", "donut", "histogram", "scatter"} <= charts and len(rec["charts"]) <= 6
    line = next(w for w in rec["charts"] if w["chart"] == "line")
    assert line["query"]["dimension"] == {"column": "When", "grain": "month"}  # span over 62 days
    assert all("Channel" not in str(w["query"]) for w in rec["kpis"] + rec["charts"])  # sensitive column left out
    for w in rec["kpis"] + rec["charts"]:
        assert w["reason"]
        aq.run(tf, Q.validate_python(w["query"]))  # every suggestion is a valid, runnable query

    short = pd.DataFrame(
        {"D": [date(2026, 1, d) for d in range(1, 21)], "V": [float(d * d) for d in range(20)]}
    ).astype(object)
    rec2 = recommend(TypedFrame(short))
    assert next(w for w in rec2["charts"] if w["chart"] == "line")["query"]["dimension"]["grain"] == "day"
    text_only = recommend(TypedFrame(pd.DataFrame({"Note": [f"note {i}" for i in range(30)]}).astype(object)))
    assert text_only["charts"] == [] and len(text_only["notes"]) == 3 and len(text_only["kpis"]) == 1
