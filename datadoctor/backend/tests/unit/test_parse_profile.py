"""Parsing into snapshots and column profiling, checked against hand counts and independent pandas maths."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from app.services.ingest.parse import normalise_headers
from app.services.profiling.profile import column_profile, dataset_profile


def test_header_normalisation_reports_every_change():
    names, changes = normalise_headers(["Amount", None, " City  name ", "amount", "Amount", 2026])
    assert names == ["Amount", "Column 2", "City name", "amount (2)", "Amount (3)", "2026"]
    assert [c["reason"] for c in changes] == ["blank", "whitespace", "duplicate", "duplicate"]


def test_numeric_profile_matches_numpy():
    raw = pd.Series([10, 20.5, "Rs 1,000", "(5)", None, "12,34,567", "N/A", 7], dtype=object)
    p = column_profile("Amount", raw)
    expected = np.array([10, 20.5, 1000, -5, 1234567, 7], dtype=float)
    num = p["numeric"]
    assert p["type"] == "number" and p["family"] == "number"
    assert num["count"] == 6 and num["stored_as_text"] == 3
    assert num["min"] == expected.min() and num["max"] == expected.max()
    assert num["mean"] == pytest.approx(expected.mean())
    assert num["median"] == pytest.approx(np.median(expected))
    assert num["std"] == pytest.approx(expected.std(ddof=1))
    assert num["negatives"] == 1
    assert sum(b["count"] for b in num["histogram"]) == 6
    assert p["missing"] == 2 and p["missing_kinds"]["null_token"] == 1 and p["missing_kinds"]["empty"] == 1


def test_integer_and_mixed_detection():
    ints = column_profile("Qty", pd.Series([1, 2, "3", 4], dtype=object))
    assert ints["type"] == "integer" and ints["mixed"] is False
    mixed = column_profile("Code", pd.Series([1, 2, 3, "abc", "def"] * 4, dtype=object))
    assert mixed["family"] == "number" and mixed["consistency"] == 0.6 and mixed["mixed"] is True


def test_date_profile_never_guesses_ambiguous_dates():
    raw = pd.Series(
        [dt.date(2026, 3, 1), "25/03/2026", "03/04/2026", "04/03/2026", "05/05/2026", "31/02/2026", "2026-04-05"],
        dtype=object,
    )
    p = column_profile("Date", raw, today=dt.datetime(2026, 4, 1))
    d = p["date"]
    assert p["type"] == "date"
    assert d["evidence"] == {
        "iso_or_named": 1,
        "dmy_only": 1,
        "mdy_only": 0,
        "ambiguous": 2,
        "same_either_way": 1,
        "invalid": 1,
    }
    assert d["resolved"] == 4  # native + 25/03 + 05/05 + ISO; ambiguous ones are excluded
    assert (d["min"], d["max"]) == ("2026-03-01", "2026-05-05")
    assert d["future"] == 2  # 2026-04-05 and 2026-05-05 are after the reference date
    assert "2 ambiguous" in d["range_note"]


def test_category_profile_and_top_values():
    raw = pd.Series(["Lahore", "Lahore", "Karachi", " lahore", None, "LAHORE"], dtype=object)
    p = column_profile("City", raw)
    assert p["type"] == "category"
    assert p["unique"] == 4  # raw values are not merged: that is a cleaning decision
    assert p["top_values"][0] == {"value": "Lahore", "count": 2, "pct": 40.0}
    assert p["whitespace_issues"] == 1


def test_boolean_profile():
    p = column_profile("Paid", pd.Series(["Yes", "no", True, "TRUE", "n"], dtype=object))
    assert p["type"] == "boolean" and p["boolean"] == {"true": 3, "false": 2}


def test_empty_column():
    p = column_profile("Blank", pd.Series([None, " ", "N/A"], dtype=object))
    assert p["type"] == "empty" and p["missing"] == 3


def test_dataset_profile_counts():
    df = pd.DataFrame({"a": [1, 1, None, 3], "b": ["x", "x", None, "y"], "c": [None, None, None, None]}, dtype=object)
    p = dataset_profile(df)
    assert (p["rows"], p["columns"], p["total_cells"]) == (4, 3, 12)
    assert p["missing_cells"] == 6
    assert p["duplicate_rows"] == 1
    assert p["empty_rows"] == 1
    assert p["empty_columns"] == 1
