import pytest

from tests.fixtures import builders as fx


def _session(client, data=None, name="invoices.xlsx"):
    ds = client.post("/api/uploads", files={"file": (name, data or fx.profiling_workbook())}).json()
    res = client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0})
    assert res.status_code == 201, res.text
    return res.json()


def _req(op, **params):
    return {"operation_type": op, "parameters": params}


def test_catalogue_lists_17_operations(client):
    ops = client.get("/api/cleaning/operations").json()
    assert len(ops) == 17
    assert {o["group"] for o in ops} == {"Rows", "Text", "Types & dates", "Missing values", "Columns", "Detection"}


def test_preview_changes_nothing_and_matches_apply(client):
    sess = _session(client)
    sid = sess["id"]
    pv = client.post(f"/api/sessions/{sid}/cleaning/preview", json=_req("trim_whitespace")).json()
    assert pv["affected_rows"] == 1 and pv["destructive"] is False
    assert pv["sample"][0]["before"]["City"] == " lahore" and pv["sample"][0]["after"]["City"] == "lahore"
    assert client.get(f"/api/sessions/{sid}").json()["version"] == 0  # preview wrote nothing
    applied = client.post(f"/api/sessions/{sid}/cleaning/apply", json=_req("trim_whitespace")).json()
    assert applied["result"]["affected_rows"] == pv["affected_rows"]
    assert applied["session"]["version"] == 1
    rows = client.get(f"/api/sessions/{sid}/rows?limit=10").json()
    assert rows["rows"][1][2] == "lahore"
    original = client.get(f"/api/sessions/{sid}/rows?view=original&limit=10").json()
    assert original["rows"][1][2] == " lahore"  # the original is never modified


def test_destructive_operations_require_confirmation(client):
    sid = _session(client)["id"]
    res = client.post(f"/api/sessions/{sid}/cleaning/apply", json=_req("remove_exact_duplicates"))
    assert res.status_code == 409 and res.json()["error"]["code"] == "CONFIRMATION_REQUIRED"
    res = client.post(f"/api/sessions/{sid}/cleaning/apply", json={**_req("remove_exact_duplicates"), "confirm": True})
    assert res.status_code == 200 and res.json()["session"]["rows"] == 7
    # Row identity: spreadsheet row numbers survive the removal.
    rows = client.get(f"/api/sessions/{sid}/rows?limit=10").json()
    assert rows["row_numbers"] == [2, 3, 4, 5, 7, 8, 9]  # duplicate of INV-4 was on spreadsheet row 6


def test_nothing_to_change_is_not_recorded(client):
    sid = _session(client)["id"]
    client.post(f"/api/sessions/{sid}/cleaning/apply", json=_req("trim_whitespace"))
    res = client.post(f"/api/sessions/{sid}/cleaning/apply", json=_req("trim_whitespace"))
    assert res.status_code == 422 and res.json()["error"]["code"] == "NOTHING_TO_CHANGE"
    assert len(client.get(f"/api/sessions/{sid}/history").json()) == 1


def test_date_rule_resolves_ambiguity_issue(client):
    sid = _session(client)["id"]
    before = client.get(f"/api/sessions/{sid}/profile").json()
    assert any(i["code"] == "Q11" for i in before["issues"])
    res = client.post(
        f"/api/sessions/{sid}/cleaning/apply", json=_req("normalize_dates", column="Date", interpretation="DMY")
    )
    body = res.json()
    assert res.status_code == 200, body
    assert body["result"]["failure_count"] == 1  # 31/02/2026
    assert body["result"]["failures"][0]["row"] == 8
    after = client.get(f"/api/sessions/{sid}/profile").json()
    codes = {i["code"] for i in after["issues"] if i["column"] == "Date"}
    assert "Q11" not in codes and "Q10" not in codes and "Q12" not in codes
    assert after["column_profiles"][1]["date"]["native"] == 6


def test_rename_carries_sensitive_marking(client):
    data = fx.csv_bytes(
        rows=[["CNIC", "Amount"], ["35202-1234567-1", "1"], ["42101-7654321-3", "2"], ["61101-1111111-5", "3"]]
    )
    sid = _session(client, data, "p.csv")["id"]
    client.put(f"/api/sessions/{sid}/sensitive-columns", json={"columns": ["CNIC"]})
    res = client.post(
        f"/api/sessions/{sid}/cleaning/apply", json=_req("rename_columns", mapping={"CNIC": "National ID"})
    )
    assert res.status_code == 200
    assert client.get(f"/api/sessions/{sid}/profile").json()["sensitive_columns"] == ["National ID"]


def test_category_suggestions_endpoint(client):
    sid = _session(client)["id"]
    res = client.get(f"/api/sessions/{sid}/cleaning/category-suggestions?column=City").json()
    assert res["groups"][0]["suggested"] == "Lahore"
    assert client.get(f"/api/sessions/{sid}/cleaning/category-suggestions?column=Nope").status_code == 422


@pytest.mark.parametrize("path", ["cleaning/preview", "cleaning/apply"])
def test_other_workspaces_cannot_clean(client, other_client, path):
    sid = _session(client)["id"]
    other_client.get("/api/settings")
    assert other_client.post(f"/api/sessions/{sid}/{path}", json=_req("trim_whitespace")).status_code == 404


def test_invalid_requests(client):
    sid = _session(client)["id"]
    res = client.post(f"/api/sessions/{sid}/cleaning/preview", json=_req("trim_whitespace", columns=["Nope"]))
    assert res.status_code == 422 and res.json()["error"]["code"] == "INVALID_OPERATION"
    res = client.post(f"/api/sessions/{sid}/cleaning/preview", json=_req("nuke"))
    assert res.json()["error"]["code"] == "UNKNOWN_OPERATION"


def test_preview_marks_type_conversions_with_unchanged_text(client):
    sid = _session(client)["id"]
    pv = client.post(
        f"/api/sessions/{sid}/cleaning/preview", json=_req("normalize_dates", column="Date", interpretation="DMY")
    ).json()
    iso_rows = [r for r in pv["sample"] if r["before"].get("Date") == "2026-04-05"]
    assert iso_rows and all(r["converted"] == ["Date"] for r in iso_rows)
    assert all(r["converted"] == [] for r in pv["sample"] if r["before"].get("Date") == "25/03/2026")
