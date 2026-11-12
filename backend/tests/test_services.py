import pandas as pd
import pytest

from app.services import analysis, cleaning, ingest, insights


def frame():
    return pd.DataFrame({
        "Date": ["01/02/2025", "02/02/2025", "02/02/2025", "13/02/2025", "bad", " 14/02/2025 "],
        "Units (kWh)": ["10", "12 kWh", "12 kWh", "1,100", "9", None],
        "Amount": ["Rs 500", "600", "600", "", "450", "700"],
        "Room": [" Kitchen", "Kitchen", "Kitchen", "Lounge", "Lounge", "Lounge"],
    })


def test_parse_numeric_handles_units_and_separators():
    s = ingest.parse_numeric(pd.Series(["1,234.5 kWh", "Rs. 500", "(20)", "n/a", None]))
    assert s.tolist()[:3] == [1234.5, 500.0, -20.0]
    assert s.isna().tolist()[3:] == [True, True]


def test_dayfirst_detected_and_mapping_guessed():
    df = frame()
    m = ingest.detect_mapping(df)
    assert m["timestamp"] == "Date"
    assert m["consumption"] == "Units (kWh)"
    assert m["cost"] == "Amount"
    assert m["category"] == "Room"
    assert m["dayfirst"] is True
    ts = ingest.parse_datetime(df["Date"], True)
    assert ts.iloc[3] == pd.Timestamp("2025-02-13")


def test_suggestions_are_counted_from_data():
    df = frame()
    m = ingest.detect_mapping(df)
    by_id = {s["id"]: s for s in cleaning.suggest(df, m)}
    assert by_id["drop_duplicates"]["affected_rows"] == 1
    assert by_id["drop_invalid_dates"]["affected_rows"] == 1
    assert by_id["drop_missing_consumption"]["affected_rows"] == 1
    assert by_id["trim_text"]["affected_rows"] == 2


def test_cleaning_pipeline_and_log():
    df = frame()
    m = ingest.detect_mapping(df)
    out, log = cleaning.apply(df, m, ["trim_text", "drop_duplicates", "drop_invalid_dates", "drop_missing_consumption"])
    assert len(out) == 3
    assert out["Units (kWh)"].tolist() == [10.0, 12.0, 1100.0]
    assert [l["action"] for l in log] == ["trim_text", "drop_duplicates", "parse_types", "drop_invalid_dates",
                                          "drop_missing_consumption"]
    assert set(out["Room"]) == {"Kitchen", "Lounge"}


def test_conflicting_actions_rejected():
    df = frame()
    with pytest.raises(ValueError):
        cleaning.apply(df, ingest.detect_mapping(df), ["drop_missing_consumption", "interpolate_missing_consumption"])


def test_cumulative_readings_detected_and_converted():
    df = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=10).astype(str),
                       "reading": [5000 + i * 12 for i in range(10)]})
    m = ingest.detect_mapping(df)
    assert any(s["id"] == "cumulative_to_delta" for s in cleaning.suggest(df, m))
    out, _ = cleaning.apply(df, m, ["cumulative_to_delta"])
    assert out["reading"].tolist() == [12.0] * 9


def test_analysis_totals_match_source():
    idx = pd.date_range("2025-01-01", periods=24 * 20, freq="h")
    kwh = [1.0] * len(idx)
    kwh[24 * 5 + 3] = 50.0  # spike on day 6
    df = pd.DataFrame({"ts": idx, "kwh": kwh})
    m = {"timestamp": "ts", "consumption": "kwh"}
    a = analysis.analyze(df, m, {"tariff_per_kwh": 10, "currency": "Rs"})
    assert a["summary"]["total_kwh"] == pytest.approx(sum(kwh))
    assert a["summary"]["total_cost"] == pytest.approx(sum(kwh) * 10)
    assert a["summary"]["granularity"] == "hourly"
    assert a["anomalies"][0]["date"] == "2025-01-06"
    assert a["peak_hours"]["share_pct"] is not None
    assert any(f["id"] == "anomalies" for f in a["facts"])


def test_verifier_drops_invented_numbers(monkeypatch):
    idx = pd.date_range("2025-01-01", periods=30, freq="D")
    df = pd.DataFrame({"ts": idx, "kwh": [10.0 + (i % 3) for i in range(30)]})
    a = analysis.analyze(df, {"timestamp": "ts", "consumption": "kwh"}, {"currency": "Rs"})
    total = a["summary"]["total_kwh"]

    fake = {
        "summary": f"You used {total} kWh in total.",
        "insights": [
            {"title": "Good", "explanation": f"Total use was {total:,.0f} kWh.", "fact_ids": ["total", "nope"]},
            {"title": "Invented", "explanation": "You could save 4,321 kWh by switching off lights.", "fact_ids": ["total"]},
            {"title": "Fake date", "explanation": "Usage peaked on 2030-01-01.", "fact_ids": ["peak_day"]},
        ],
        "recommendations": [{"action": "Shift laundry to off-peak hours", "why": "Peak hours cost more.", "fact_ids": []}],
    }
    monkeypatch.setattr(insights.settings.__class__, "ai_enabled", property(lambda self: True))
    monkeypatch.setattr(insights, "_chat", lambda system, payload: fake)
    out = insights.insights(a)
    assert out["source"] == "groq"
    titles = [i["title"] for i in out["insights"]]
    assert titles == ["Good"]
    assert out["insights"][0]["fact_ids"] == ["total"]
    assert len(out["removed"]) == 2
    assert len(out["recommendations"]) == 1


def test_rule_based_without_key():
    idx = pd.date_range("2025-01-01", periods=30, freq="D")
    df = pd.DataFrame({"ts": idx, "kwh": [10.0] * 30})
    a = analysis.analyze(df, {"timestamp": "ts", "consumption": "kwh"}, {})
    out = insights.insights(a)
    assert out["source"] == "rules"
    assert "300 kWh" in out["summary"]
