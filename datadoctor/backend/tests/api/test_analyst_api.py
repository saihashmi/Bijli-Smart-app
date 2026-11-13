"""M11–M12: AI Analyst. Local interpreter, allowlist, verified explanations, privacy rules, history."""

import json

import pytest

from app.config import settings
from app.services.analyst import provider
from app.services.analyst.verify import verify
from tests.fixtures import builders as fx


def _sales() -> bytes:
    rows = [["Order", "Date", "Region", "Channel", "Units", "Amount", "Email"]]
    regions, channels = ["North", "South", "East"], ["Online", "Shop"]
    import datetime as dt

    for i in range(60):
        units = (i % 7) + 1
        amount = None if i in (9, 39) else 100 * (i % 5 + 1) + units * 10
        rows.append(
            [
                f"O-{i + 1}",
                dt.date(2026, 1 + (i % 4), 1 + (i % 27)),
                regions[i % 3],
                channels[i % 2],
                units,
                amount,
                f"p{i}@example.com",
            ]
        )
    return fx.xlsx_from_rows(rows, title="Sales")


@pytest.fixture
def sid(client):
    ds = client.post("/api/uploads", files={"file": ("sales.xlsx", _sales())}).json()
    return client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0}).json()["id"]


def ask(client, sid, question=None, **body):
    res = client.post(f"/api/sessions/{sid}/analyst/ask", json={"question": question, **body} if question else body)
    assert res.status_code == 200, res.text
    return res.json()


# Hand-counted: Amount by region North 5,710, South 6,780, East 6,770; total 19,260 over 58 values.
@pytest.mark.parametrize(
    "question,operation,params,expected",
    [
        ("How many records are there?", "count_rows", {}, "There are 60 rows."),
        (
            "What is the total amount?",
            "aggregate",
            {"measure": "Amount", "agg": "sum"},
            "is 19,260, calculated from 58 values",
        ),
        ("average of Units", "aggregate", {"measure": "Units", "agg": "avg"}, "The average of “Units” is"),
        (
            "Which region has the highest total amount?",
            "group_rank",
            {"group_by": "Region", "measure": "Amount", "agg": "sum", "order": "desc"},
            "“South” has the highest total of “Amount” among “Region” groups: 6,780.",
        ),
        (
            "Which channel has the fewest records?",
            "group_rank",
            {"group_by": "Channel", "agg": "count", "order": "asc"},
            "share the lowest number of rows (30): Online, Shop",
        ),
        (
            "Show the monthly trend of amount",
            "time_trend",
            {"date_col": "Date", "grain": "month", "measure": "Amount", "agg": "sum"},
            "covers 4 periods, from 2026-01",
        ),
        (
            "Which month has the highest amount?",
            "extreme_period",
            {"date_col": "Date", "grain": "month", "which": "max"},
            "has the highest total of “Amount”",
        ),
        (
            "Compare North and South by total amount",
            "compare_groups",
            {"group_by": "Region", "values": ["North", "South"]},
            "“South” is higher than “North” by 1,070.",
        ),
        (
            "How is amount distributed?",
            "distribution",
            {"column": "Amount"},
            "“Amount” has 58 numeric values from 110 to 570.",
        ),
        (
            "Is units related to amount?",
            "correlation",
            {"x": "Units", "y": "Amount"},
            "based on 58 rows that have both values",
        ),
        ("Which columns contain missing values?", "missing_summary", {}, "“Amount” has the most: 2 of 60 rows"),
        ("Are there duplicates?", "duplicate_summary", {}, "No row is an exact copy of another among the 60 rows."),
        (
            "Describe the Region column",
            "column_profile",
            {"column": "Region"},
            "“Region” is a category column with 60 filled and 0 missing",
        ),
        (
            "Explain the anomalies in amount",
            "outlier_summary",
            {"column": "Amount"},
            "No value in “Amount” lies outside the typical range",
        ),
        (
            "Suggest the best charts for this dataset",
            "chart_suggestions",
            {},
            "charts fit this data, chosen from the column types only.",
        ),
        ("Why is my score low?", "quality_explain", {}, "The Data Health Score is"),
    ],
)
def test_local_interpreter_answers_every_allowlisted_operation(client, sid, question, operation, params, expected):
    out = ask(client, sid, question)
    assert out["status"] == "answered", out
    assert out["interpreter"] == "local" and out["explanation"] is None
    assert out["answer"]["operation"] == operation
    for key, value in params.items():
        assert out["answer"]["params"][key] == value, key
    assert expected in out["answer"]["answer"], out["answer"]["answer"]


def test_answers_carry_tables_charts_and_exclusion_notes(client, sid):
    out = ask(client, sid, "Which region has the highest total amount?")["answer"]
    assert out["table"]["rows"] == [["South", "6,780", "20"], ["East", "6,770", "20"], ["North", "5,710", "20"]]
    assert out["chart"]["chart"] == "bar" and out["chart"]["result"]["rows"][0]["value"] == 6780
    assert out["notes"] == ["2 rows have no value in “Amount” and are not counted as zero."]
    trend = ask(client, sid, "Show the monthly trend of amount")["answer"]
    assert trend["chart"]["chart"] == "line" and "it is not a forecast" in trend["answer"]


def test_unanswerable_questions_get_an_honest_reply(client, sid):
    for question in ["What will sales be next year?", "Who is the best manager?", "asdf qwer"]:
        out = ask(client, sid, question)
        assert out["status"] == "cannot_answer" and out["answer"] is None
        assert out["message"] == "I can't answer that with this data or the supported operations."
        assert len(out["alternatives"]) == 4 and all(a["operation"] for a in out["alternatives"])
    unclear = ask(client, sid, "show the distribution")
    assert unclear["status"] == "cannot_answer" and "could not tell which numeric column" in unclear["message"]
    assert "“Amount”" in unclear["message"] and "“Units”" in unclear["message"]


def test_guided_builder_runs_validated_operations_only(client, sid):
    out = ask(client, sid, operation="group_rank", params={"group_by": "Region", "measure": "Amount", "agg": "median"})
    assert out["status"] == "answered" and out["interpreter"] == "guided"
    assert "median of “Amount”" in out["answer"]["answer"]

    bad_column = ask(client, sid, operation="aggregate", params={"measure": "Nope", "agg": "sum"})
    assert bad_column["status"] == "cannot_answer" and bad_column["message"] == "There is no column called “Nope”."
    not_allowed = ask(client, sid, operation="aggregate", params={"measure": "Region", "agg": "sum"})
    assert not_allowed["status"] == "cannot_answer" and "cannot be used on “Region”" in not_allowed["message"]
    for operation, params in [
        ("run_python", {"code": "import os"}),
        ("sql", {"query": "select * from t"}),
        ("aggregate", {"measure": "Amount", "agg": "sum", "code": "x"}),
        ("aggregate", {"measure": "Amount", "agg": "exec"}),
    ]:
        out = ask(client, sid, operation=operation, params=params)
        assert out["status"] == "cannot_answer" and out["answer"] is None


def test_catalogue_suggestions_and_history(client, sid, other_client):
    cat = client.get("/api/analyst/operations").json()
    assert len(cat["operations"]) == 14 and cat["ai"] == {"configured": False, "provider": None, "model": None}
    assert len(cat["limitations"]) == 3

    tips = client.get(f"/api/sessions/{sid}/analyst/suggestions").json()["suggestions"]
    assert tips[0]["question"] == "How many rows are there?"
    assert any(t["question"] == "Which Region has the highest total Amount?" for t in tips)
    for t in tips:  # every suggestion really works
        assert ask(client, sid, operation=t["operation"], params=t["params"])["status"] == "answered", t

    ask(client, sid, "What is the total amount?")
    ask(client, sid, "What will sales be next year?")
    hist = client.get(f"/api/sessions/{sid}/analyst/history").json()["interactions"]
    assert hist[0]["question"] == "What will sales be next year?" and hist[0]["operation"] is None
    assert hist[1]["operation"] == "aggregate" and hist[1]["params"]["measure"] == "Amount"
    assert hist[1]["summary"].startswith("The total of “Amount” is 19,260") and hist[1]["provider"] == "local"

    assert other_client.get(f"/api/sessions/{sid}/analyst/history").status_code == 404
    assert other_client.post(f"/api/sessions/{sid}/analyst/ask", json={"question": "How many rows?"}).status_code == 404
    assert client.post(f"/api/sessions/{sid}/analyst/ask", json={}).status_code == 422
    assert client.post(f"/api/sessions/{sid}/analyst/ask", json={"question": "x" * 501}).status_code == 422


# ---------- optional AI layer (provider mocked: no network in tests) ----------
@pytest.fixture
def ai(monkeypatch):
    calls = []
    script = {"choose": None, "explain": None, "fail": False}

    def fake_chat(messages, json_mode, transport=None):
        calls.append({"json_mode": json_mode, "messages": messages})
        if script["fail"]:
            raise provider.ProviderError("timeout")
        return json.dumps(script["choose"]) if json_mode else script["explain"]

    monkeypatch.setattr(type(settings), "ai_configured", property(lambda self: True))  # settings are frozen
    monkeypatch.setattr(provider, "_chat", fake_chat)
    return calls, script


def test_ai_chooses_an_operation_and_a_faithful_explanation_is_accepted(client, sid, ai):
    calls, script = ai
    script["choose"] = {"operation": "group_rank", "params": {"group_by": "Region", "measure": "Amount", "agg": "sum"}}
    script["explain"] = "“South” leads with a total of 6,780, ahead of the other 2 groups out of 3."
    out = ask(client, sid, "Where do we earn the most?")
    assert out["interpreter"] == "groq" and out["answer"]["operation"] == "group_rank"
    assert out["answer"]["table"]["rows"][0] == ["South", "6,780", "20"]  # computed locally, not by the model
    assert out["explanation"] == {
        "text": script["explain"],
        "provider": "groq",
        "model": settings.groq_model,
        "status": "verified",
    }
    sent = json.dumps([c["messages"] for c in calls])
    assert "example.com" not in sent and "O-1" not in sent  # no row content is sent
    first = json.loads(calls[0]["messages"][1]["content"])
    assert {"name": "Amount", "type": "number"} in first["columns"]
    hist = client.get(f"/api/sessions/{sid}/analyst/history").json()["interactions"][0]
    assert hist["provider"] == "groq" and hist["explanation_status"] == "verified"


@pytest.mark.parametrize(
    "text",
    [
        "South leads with 7,000.",  # a number that was never computed
        "“West” leads with 6,780.",  # a label that is not in the result
        "South leads with 6,780, which is double the others.",  # a quantity in words
        "South peaked in 2027-03 with 6,780.",  # a date that is not in the result
    ],
)
def test_ai_explanations_that_add_anything_are_rejected(client, sid, ai, text):
    _, script = ai
    script["choose"] = {"operation": "group_rank", "params": {"group_by": "Region", "measure": "Amount", "agg": "sum"}}
    script["explain"] = text
    out = ask(client, sid, "Where do we earn the most?")
    assert out["status"] == "answered" and out["explanation"] is None
    assert any("so it was discarded" in n for n in out["notices"])
    assert "6,780" in out["answer"]["answer"]  # the built-in explanation is still there
    assert (
        client.get(f"/api/sessions/{sid}/analyst/history").json()["interactions"][0]["explanation_status"] == "rejected"
    )


def test_ai_cannot_run_anything_outside_the_allowlist(client, sid, ai):
    _, script = ai
    script["explain"] = "ok"
    for choice in [
        {"operation": "run_python", "params": {"code": "__import__('os').system('id')"}},
        {"operation": "aggregate", "params": {"measure": "Amount", "agg": "sum", "sql": "drop table x"}},
        {"operation": "aggregate", "params": {"measure": "Secret", "agg": "sum"}},
    ]:
        script["choose"] = choice
        out = ask(client, sid, "What will sales be next year?")
        assert out["status"] == "cannot_answer" and out["answer"] is None
    # when the local rules do understand the question, they take over
    script["choose"] = {"operation": "run_python", "params": {}}
    out = ask(client, sid, "What is the total amount?")
    assert out["status"] == "answered" and out["interpreter"] == "local"
    assert any("did not fit this data" in n for n in out["notices"])


def test_provider_failure_falls_back_with_a_visible_notice(client, sid, ai):
    _, script = ai
    script["fail"] = True
    out = ask(client, sid, "What is the total amount?")
    assert out["status"] == "answered" and out["interpreter"] == "local" and out["explanation"] is None
    assert out["notices"][0] == "The AI service was unavailable, so the built-in interpreter was used instead."
    assert "19,260" in out["answer"]["answer"]


def test_sensitive_columns_and_hidden_names_never_reach_the_provider(client, sid, ai):
    calls, script = ai
    client.put(f"/api/sessions/{sid}/sensitive-columns", json={"columns": ["Email", "Region"]})
    script["choose"] = {"operation": None, "params": {}}
    script["explain"] = "x"
    out = ask(client, sid, "Which region has the highest total amount?")
    listed = json.loads(calls[0]["messages"][1]["content"])["columns"]
    assert [c["name"] for c in listed] == ["Order", "Date", "Channel", "Units", "Amount"]  # sensitive ones left out
    assert out["status"] == "answered" and out["interpreter"] == "local" and out["explanation"] is None
    assert out["notices"] == ["This answer uses a column marked as sensitive, so nothing was sent to the AI service."]
    assert len(calls) == 1  # no explanation request was made

    calls.clear()
    client.put(f"/api/sessions/{sid}/sensitive-columns", json={"columns": []})
    client.put("/api/settings", json={"ai_share_column_names": False})
    script["choose"] = {"operation": "aggregate", "params": {"measure": "col_6", "agg": "sum"}}
    out = ask(client, sid, "add up the money")
    listed = json.loads(calls[0]["messages"][1]["content"])["columns"]
    assert [c["name"] for c in listed] == [f"col_{i}" for i in range(1, 8)] and "Amount" not in json.dumps(calls)
    assert out["interpreter"] == "groq" and out["answer"]["params"]["measure"] == "Amount"  # alias mapped back locally
    assert out["explanation"] is None and "Column names are not shared" in out["notices"][0]
    assert len(calls) == 1


def test_verifier_unit():
    answer = {
        "answer": "“South” has the highest total: 6,780.50 from 20 rows in 2026-03.",
        "notes": [],
        "table": {"columns": ["Region"], "rows": [["South", "6,780.5"]]},
    }
    assert verify("South is highest at 6780.5, from 20 rows.", answer) == (True, None)
    assert verify("“South” reached 6,780.50 in 2026-03.", answer)[0]
    assert not verify("South is highest at 6,781.", answer)[0]
    assert not verify("", answer)[0]
    assert not verify("x" * 1300, answer)[0]
    assert not verify("South had 6,780.50 in 2026-04.", answer)[0]
