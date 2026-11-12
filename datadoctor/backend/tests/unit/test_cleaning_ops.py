"""Each of the 17 cleaning operations (SPEC §11) against hand-computed expectations."""

import datetime as dt

import pandas as pd
import pytest

from app.errors import AppError
from app.services.cleaning import engine
from app.services.cleaning.ops import category_suggestions, parse_date, parse_number


def frame(**cols):
    return pd.DataFrame(cols, dtype=object)


def run(df, op, **params):
    return engine.run(df, op, params, {"header_row": 0})[2]


def col(result, name):
    return result.df[name].tolist()


def test_remove_exact_duplicates_keeps_row_identity():
    df = frame(a=[1, 1, 2, 1], b=["x", "x", "y", "x"])
    r = run(df, "remove_exact_duplicates")
    assert r.affected_rows == 2 and list(r.df.index) == [0, 2]
    r = run(df, "remove_exact_duplicates", keep="last")
    assert list(r.df.index) == [2, 3]


def test_key_duplicates_flag_by_default_and_remove_on_request():
    df = frame(id=["A", "B", "A", "C", "B"], amount=[1, 2, 3, 4, 5])
    flagged = run(df, "key_duplicates", key_columns=["id"])
    assert col(flagged, "is_duplicate_key") == [False, False, True, False, True]
    assert len(flagged.df) == 5 and flagged.affected_rows == 2
    removed = run(df, "key_duplicates", key_columns=["id"], mode="remove")
    assert list(removed.df.index) == [0, 1, 3]


def test_trim_and_normalise_spaces_only_touch_text():
    df = frame(city=["  Lahore ", "Port  Qasim", 5, None, " Multan"])
    t = run(df, "trim_whitespace")
    assert col(t, "city") == ["Lahore", "Port  Qasim", 5, None, "Multan"] and t.affected_rows == 2
    s = run(df, "normalize_spaces", columns=["city"])
    assert col(s, "city")[1] == "Port Qasim"


@pytest.mark.parametrize(
    ("style", "expected"),
    [("upper", "LAHORE CANTT"), ("lower", "lahore cantt"), ("title", "Lahore Cantt"), ("sentence", "Lahore cantt")],
)
def test_standardize_case(style, expected):
    r = run(frame(c=["laHore CANTT"]), "standardize_case", style=style)
    assert col(r, "c") == [expected]


def test_category_suggestions_and_normalisation():
    df = frame(city=["Lahore", "Lahore", " lahore", "LAHORE", "Karachi"])
    groups = category_suggestions(df["city"])
    # Most frequent first; ties prefer no edge spaces, so "LAHORE" is listed before " lahore".
    assert groups == [
        {
            "suggested": "Lahore",
            "variants": [
                {"label": "Lahore", "count": 2},
                {"label": "LAHORE", "count": 1},
                {"label": " lahore", "count": 1},
            ],
        }
    ]
    r = run(df, "normalize_categories", column="city", mapping={" lahore": "Lahore", "LAHORE": "Lahore"})
    assert col(r, "city") == ["Lahore", "Lahore", "Lahore", "Lahore", "Karachi"] and r.affected_rows == 2


@pytest.mark.parametrize(
    ("text", "kwargs", "expected"),
    [
        ("Rs 1,250.50", {}, 1250.5),
        ("12,34,567", {}, 1234567),
        ("(250)", {}, -250),
        ("(250)", {"parentheses_negative": False}, 250),
        ("15%", {}, 15),
        ("15%", {"percent": "divide_by_100"}, 0.15),
        ("1.234,56", {"decimal": ","}, 1234.56),
        ("500-", {}, -500),
        ("PKR 7", {}, 7),
        ("abc", {}, None),
        ("12-15", {}, None),
    ],
)
def test_parse_number(text, kwargs, expected):
    got = parse_number(text, **kwargs)
    assert got == pytest.approx(expected) if expected is not None else got is None


def test_convert_numeric_reports_failures_and_never_zero_fills():
    df = frame(amount=["Rs 1,000", 250, "abc", None, "N/A", "(5)"])
    r = run(df, "convert_numeric", columns=["amount"])
    assert col(r, "amount") == [1000, 250, None, None, None, -5]
    assert r.failure_count == 1 and r.failures[0]["value"] == "abc"
    kept = run(df, "convert_numeric", columns=["amount"], on_failure="keep_raw_column")
    assert col(kept, "amount__raw")[2] == "abc"


@pytest.mark.parametrize(
    ("value", "interp", "expected", "reason"),
    [
        ("03/04/2026", "DMY", dt.datetime(2026, 4, 3), None),
        ("03/04/2026", "MDY", dt.datetime(2026, 3, 4), None),
        ("25/03/2026", "MDY", None, "Only valid as DD/MM"),
        ("31/02/2026", "DMY", None, "Not a valid date"),
        ("2026-04-05", "MDY", dt.datetime(2026, 4, 5), None),
        ("12-Jan-2025", "DMY", dt.datetime(2025, 1, 12), None),
        ("05/06/26", "DMY", dt.datetime(2026, 6, 5), None),
        (45658, "excel_serial_1900", dt.datetime(2025, 1, 1), None),
        (45658, "DMY", None, "A number, not a date"),
        ("hello", "DMY", None, "Not recognised"),
    ],
)
def test_parse_date_uses_only_the_confirmed_reading(value, interp, expected, reason):
    got, why = parse_date(value, interp)
    assert got == expected
    if reason:
        assert why.startswith(reason)


def test_normalize_dates_records_the_rule_and_reports_contradictions():
    df = frame(d=["03/04/2026", dt.date(2026, 1, 2), "25/03/2026", "2026-02-01", None, "31/02/2026"])
    r = run(df, "normalize_dates", column="d", interpretation="DMY")
    assert col(r, "d") == [
        dt.date(2026, 4, 3),
        dt.date(2026, 1, 2),
        dt.date(2026, 3, 25),
        dt.date(2026, 2, 1),
        None,
        None,
    ]
    assert r.failure_count == 1 and r.date_rule == ("d", "DMY")
    mdy = run(df, "normalize_dates", column="d", interpretation="MDY")
    assert mdy.failure_count == 2  # 25/03 contradicts MM/DD; 31/02 is impossible
    assert {f["reason"][:9] for f in mdy.failures} == {"Only vali", "Not a val"}


def test_identify_invalid_dates_does_not_change_values():
    df = frame(d=["03/04/2026", "31/02/2026", "soon", None])
    r = run(df, "identify_invalid_dates", column="d")
    assert col(r, "d") == df["d"].tolist()
    assert col(r, "d__invalid_date") == [False, True, True, False]


def test_detect_missing_with_extra_tokens():
    df = frame(c=["N/A", "  ", "TBD", "ok", "-"])
    r = run(df, "detect_missing", extra_null_tokens=["tbd"])
    assert col(r, "c") == [None, None, None, "ok", None] and r.affected_rows == 4


def test_handle_missing_strategies():
    df = frame(n=[1, None, 3, "N/A", 10], c=["a", None, "b", "a", " "])
    assert col(run(df, "handle_missing", column="n", strategy="median"), "n") == [1, 3, 3, 3, 10]
    assert col(run(df, "handle_missing", column="n", strategy="mean"), "n")[1] == pytest.approx(14 / 3)
    assert col(run(df, "handle_missing", column="n", strategy="fixed", value="0"), "n") == [1, 0, 3, 0, 10]
    assert col(run(df, "handle_missing", column="c", strategy="mode"), "c") == ["a", "a", "b", "a", "a"]
    dropped = run(df, "handle_missing", column="n", strategy="drop_rows")
    assert list(dropped.df.index) == [0, 2, 4]
    assert run(df, "handle_missing", column="n", strategy="leave").affected_rows == 0
    with pytest.raises(AppError):
        run(df, "handle_missing", column="c", strategy="median")
    with pytest.raises(AppError):
        run(df, "handle_missing", column="n", strategy="fixed")  # no value given: never assumes zero


def test_remove_empty_rows():
    df = frame(a=[1, None, " "], b=["x", None, "N/A"])
    r = run(df, "remove_empty_rows")
    assert list(r.df.index) == [0] and r.removed_rows == 2


def test_rename_reorder_remove_columns():
    df = frame(a=[1], b=[2], c=[3])
    r = run(df, "rename_columns", mapping={"a": " Amount  PKR "})
    assert list(r.df.columns) == ["Amount PKR", "b", "c"] and r.renamed == {"a": "Amount PKR"}
    with pytest.raises(AppError):
        run(df, "rename_columns", mapping={"a": "B"})  # case-insensitive clash with b
    assert list(run(df, "reorder_columns", order=["c", "a", "b"]).df.columns) == ["c", "a", "b"]
    with pytest.raises(AppError):
        run(df, "reorder_columns", order=["c", "a"])
    assert list(run(df, "remove_columns", columns=["b"]).df.columns) == ["a", "c"]
    with pytest.raises(AppError):
        run(df, "remove_columns", columns=["a", "b", "c"])


def test_flag_outliers_and_types():
    df = frame(n=list(range(1, 21)) + [1000])
    r = run(df, "flag_outliers", column="n")
    assert col(r, "n__outlier")[-1] is True and sum(col(r, "n__outlier")) == 1
    t = run(frame(x=[1, "2", "two", None]), "flag_types", column="x")
    assert col(t, "x__type") == ["Number", "Number (as text)", "Text", "Empty"]
    assert t.affected_rows == 1


def test_unknown_operation_and_bad_parameters():
    with pytest.raises(AppError) as e:
        engine.validate("format_disk", {})
    assert e.value.code == "UNKNOWN_OPERATION"
    with pytest.raises(AppError) as e:
        engine.validate("normalize_dates", {"column": "d", "interpretation": "guess"})
    assert e.value.code == "INVALID_PARAMETERS"
    with pytest.raises(AppError) as e:
        engine.validate("trim_whitespace", {"columns": [], "evil": "x"})
    assert e.value.code == "INVALID_PARAMETERS"


def test_operations_never_modify_their_input():
    df = frame(a=[" x", None, " x"], b=[1, 2, 1])
    copy = df.copy()
    for op, p in [
        ("trim_whitespace", {}),
        ("remove_exact_duplicates", {}),
        ("handle_missing", {"column": "a", "strategy": "drop_rows"}),
    ]:
        run(df, op, **p)
    pd.testing.assert_frame_equal(df, copy)
