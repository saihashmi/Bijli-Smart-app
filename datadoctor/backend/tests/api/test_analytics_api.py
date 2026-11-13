"""M9: analytics API. Hand-counted figures on the small invoices sheet, dashboard persistence and ownership."""

from tests.fixtures import builders as fx

COUNT = {"kind": "aggregate", "measure": {"agg": "count"}}
SUM_AMOUNT = {"kind": "aggregate", "measure": {"agg": "sum", "column": "Amount"}}


def _session(client):
    ds = client.post("/api/uploads", files={"file": ("invoices.xlsx", fx.profiling_workbook())}).json()
    return client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0}).json()["id"]


def _run(client, sid, *queries, filters=None):
    res = client.post(f"/api/sessions/{sid}/analytics/query", json={"queries": list(queries), "filters": filters or []})
    assert res.status_code == 200, res.text
    return res.json()["results"]


def test_fields_describe_what_each_column_can_do(client):
    sid = _session(client)
    body = client.get(f"/api/sessions/{sid}/analytics/fields").json()
    f = {x["name"]: x for x in body["fields"]}
    assert body["rows"] == 8 and body["version"] == 0
    assert f["Amount"]["kind"] == "number" and f["Amount"]["can_measure"] and f["Amount"]["missing"] == 5
    assert (f["Amount"]["min"], f["Amount"]["max"]) == (-250, 1250.5)
    assert f["Date"]["kind"] == "date" and f["Date"]["not_usable"] == 2  # one ambiguous, one impossible
    assert f["City"]["kind"] == "category" and f["City"]["values"][0] == "Karachi"
    assert f["Column 6"]["kind"] == "empty" and f["Column 6"]["aggregations"] == []
    assert f["Invoice"]["aggregations"] == ["count", "distinct"]


def test_hand_counted_results(client):
    sid = _session(client)
    by_city = {**SUM_AMOUNT, "dimension": {"column": "City"}, "sort": {"by": "label", "dir": "asc"}}
    by_month = {**COUNT, "dimension": {"column": "Date", "grain": "month"}}
    count, total, city, month = _run(client, sid, COUNT, SUM_AMOUNT, by_city, by_month)

    assert count["result"]["total"]["value"] == 8
    assert total["result"]["total"] == {"value": 2000.5, "n": 3}  # 1250.5 + 1000 + (250 in brackets = -250)
    assert total["result"]["meta"]["measure_missing"] == 5  # N/A twice, an empty row, #DIV/0!, blanks: never 0

    rows = {r["label"]: (r["value"], r["rows"]) for r in city["result"]["rows"]}
    assert rows == {
        " lahore": (1000, 1),  # spellings are separate groups until they are cleaned
        "Islamabad": (None, 1),
        "Karachi": (None, 3),
        "LAHORE": (-250, 1),
        "Lahore": (1250.5, 1),
        "(missing)": (None, 1),
    }
    assert [(r["label"], r["value"]) for r in month["result"]["rows"]] == [
        ("2025-01", 1),
        ("2026-03", 2),
        ("2026-04", 2),
    ]
    assert month["result"]["meta"]["dimension_not_dated"] == 2 and month["result"]["meta"]["dimension_missing"] == 1


def test_dashboard_filters_apply_to_every_query_and_errors_are_per_query(client):
    sid = _session(client)
    bad = {"kind": "aggregate", "measure": {"agg": "sum", "column": "City"}}
    count, total, failed = _run(
        client, sid, COUNT, SUM_AMOUNT, bad, filters=[{"op": "in", "column": "City", "values": ["Lahore", "LAHORE"]}]
    )
    assert count["result"]["total"]["value"] == 2 and total["result"]["total"]["value"] == 1000.5
    assert failed == {
        "ok": False,
        "error": {
            "code": "AGGREGATION_NOT_ALLOWED",
            "message": "Sum cannot be used on “City” (category). Allowed: count, distinct count.",
        },
    }


def test_results_follow_cleaning_and_undo(client):
    sid = _session(client)
    res = client.post(
        f"/api/sessions/{sid}/cleaning/apply",
        json={"operation_type": "remove_exact_duplicates", "parameters": {}, "confirm": True},
    )
    assert res.status_code == 200, res.text
    after = client.post(f"/api/sessions/{sid}/analytics/query", json={"queries": [COUNT]}).json()
    assert after["version"] == 1 and after["results"][0]["result"]["total"]["value"] == 7
    client.post(f"/api/sessions/{sid}/cleaning/undo")
    assert _run(client, sid, COUNT)[0]["result"]["total"]["value"] == 8


def test_request_validation(client):
    sid = _session(client)
    url = f"/api/sessions/{sid}/analytics/query"
    assert client.post(url, json={"queries": []}).status_code == 422
    assert client.post(url, json={"queries": [COUNT] * 17}).status_code == 422
    assert client.post(url, json={"queries": [{"kind": "sql", "text": "select 1"}]}).status_code == 422
    assert client.post(url, json={"queries": [{**COUNT, "code": "import os"}]}).status_code == 422  # no extra fields
    assert (
        client.post(url, json={"queries": [{"kind": "histogram", "column": "Amount", "bins": 1000}]}).status_code == 422
    )
    leaked = client.post(url, json={"queries": [{**COUNT, "measure": {"agg": "drop"}}]})
    assert leaked.status_code == 422 and "drop" not in leaked.text  # submitted values are not echoed


def test_recommendations_are_runnable_and_explained(client):
    sid = _session(client)
    rec = client.get(f"/api/sessions/{sid}/analytics/recommendations").json()
    widgets = rec["kpis"] + rec["charts"]
    assert rec["kpis"][0]["title"] == "Rows" and all(w["reason"] for w in widgets)
    results = _run(client, sid, *[w["query"] for w in widgets])
    assert all(r["ok"] for r in results)


def test_dashboard_is_saved_per_session_and_reports_broken_widgets(client, other_client):
    sid = _session(client)
    url = f"/api/sessions/{sid}/dashboard"
    assert client.get(url).json() == {"saved": False, "dashboard": None, "updated_at": None, "broken_widgets": []}

    config = {
        "theme": "midnight",
        "filters": [{"op": "not_in", "column": "City", "values": ["Islamabad"]}],
        "widgets": [
            {"id": "k1", "title": "Rows", "chart": "kpi", "query": COUNT, "width": 3},
            {
                "id": "b1",
                "title": "Amount by city",
                "chart": "bar",
                "query": {**SUM_AMOUNT, "dimension": {"column": "City"}},
            },
            {"id": "h1", "title": "Spread", "chart": "histogram", "query": {"kind": "histogram", "column": "Amount"}},
        ],
    }
    saved = client.put(url, json=config)
    assert saved.status_code == 200, saved.text
    loaded = client.get(url).json()
    assert loaded["saved"] and loaded["dashboard"]["theme"] == "midnight" and loaded["broken_widgets"] == []
    assert [w["id"] for w in loaded["dashboard"]["widgets"]] == ["k1", "b1", "h1"]
    assert loaded["dashboard"]["widgets"][1]["width"] == 6  # default

    # another browser cannot read or change it
    assert other_client.get(url).status_code == 404
    assert other_client.put(url, json=config).status_code == 404

    # invalid configurations are refused
    clash = {**config, "widgets": [config["widgets"][0], config["widgets"][0]]}
    assert client.put(url, json=clash).json()["error"]["code"] == "DUPLICATE_WIDGET_ID"
    wrong = {**config, "widgets": [{"id": "x", "title": "x", "chart": "scatter", "query": COUNT}]}
    assert client.put(url, json=wrong).json()["error"]["code"] == "CHART_QUERY_MISMATCH"
    assert client.put(url, json={**config, "theme": "neon"}).status_code == 422

    # removing a column the dashboard uses is reported, not hidden
    res = client.post(
        f"/api/sessions/{sid}/cleaning/apply",
        json={"operation_type": "remove_columns", "parameters": {"columns": ["Amount"]}, "confirm": True},
    )
    assert res.status_code == 200, res.text
    broken = client.get(url).json()["broken_widgets"]
    assert broken == [{"id": "b1", "missing_columns": ["Amount"]}, {"id": "h1", "missing_columns": ["Amount"]}]

    assert client.delete(url).status_code == 204
    assert client.get(url).json()["saved"] is False
