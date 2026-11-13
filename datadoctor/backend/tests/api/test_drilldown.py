"""U9: rows affected by an issue, per-cell grid flags, and the missing-value map."""

import pytest

from tests.fixtures import builders as fx


def _session(client, data=None, name="invoices.xlsx"):
    ds = client.post("/api/uploads", files={"file": (name, data or fx.profiling_workbook())}).json()
    return client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0}).json()["id"]


def test_issue_rows_match_every_issue_count(client):
    sid = _session(client)
    profile = client.get(f"/api/sessions/{sid}/profile").json()
    checked = 0
    for issue in profile["issues"]:
        res = client.get(f"/api/sessions/{sid}/issues/{issue['id']}/rows?limit=200")
        if issue["code"] in ("Q14", "Q15"):
            assert res.status_code == 422 and res.json()["error"]["code"] == "NO_ROW_VIEW"
            continue
        assert res.status_code == 200, (issue["id"], res.text)
        body = res.json()
        assert body["total"] == issue["affected_rows"], issue["id"]
        assert len(body["rows"]) == min(200, body["total"])
        checked += 1
    assert checked >= 12


def test_issue_rows_values_and_paging(client):
    sid = _session(client)
    body = client.get(f"/api/sessions/{sid}/issues/Q11:Date/rows").json()
    assert body["highlight"] == "Date" and body["columns"][0] == "Date"
    assert body["rows"] == [{"row": 4, "values": ["03/04/2026", "INV-3", "LAHORE", "(250)", "yes", None, "3"]}]
    missing = client.get(f"/api/sessions/{sid}/issues/Q03:Notes/rows?offset=5&limit=5").json()
    assert missing["total"] == 7 and len(missing["rows"]) == 2
    assert client.get(f"/api/sessions/{sid}/issues/Q99:Date/rows").status_code == 404
    assert client.get(f"/api/sessions/{sid}/issues/Q03:Nope/rows").status_code == 404


def test_csv_plain_numbers_are_not_listed_as_text_numbers(client):
    data = fx.csv_bytes(rows=[["Amount"], ["1250.5"], ["Rs 1,000"], ["12"], ["(5)"]])
    sid = _session(client, data, "a.csv")
    body = client.get(f"/api/sessions/{sid}/issues/Q08:Amount/rows").json()
    assert [r["values"][0] for r in body["rows"]] == ["Rs 1,000", "(5)"]


def test_cell_flags_missing_invalid_duplicate_and_changed(client):
    sid = _session(client)
    client.get(f"/api/sessions/{sid}/profile")  # column families come from the cached profile
    page = client.get(f"/api/sessions/{sid}/rows?flags=true&limit=20").json()
    cols = page["columns"]
    flags = {
        (page["row_numbers"][i], cols[j]): f for i, row in enumerate(page["cell_flags"]) for j, f in enumerate(row)
    }
    assert flags[(5, "Amount")] == "m"  # N/A
    assert flags[(8, "Date")] == "i"  # 31/02/2026
    assert flags[(4, "Date")] == ""  # ambiguous is not invalid
    assert flags[(2, "Invoice")] == ""
    assert page["row_flags"] == ["", "", "", "d", "d", "", "", ""]  # INV-4 twice

    client.post(f"/api/sessions/{sid}/cleaning/apply", json={"operation_type": "trim_whitespace", "parameters": {}})
    client.post(
        f"/api/sessions/{sid}/cleaning/apply",
        json={"operation_type": "rename_columns", "parameters": {"mapping": {"City": "Town"}}},
    )
    client.get(f"/api/sessions/{sid}/profile")
    page = client.get(f"/api/sessions/{sid}/rows?flags=true&limit=20").json()
    town = page["columns"].index("Town")
    assert page["cell_flags"][1][town] == "c"  # " lahore" → "lahore", followed through the rename
    assert page["cell_flags"][0][town] == ""
    plain = client.get(f"/api/sessions/{sid}/rows?limit=5").json()
    assert plain["cell_flags"] is None  # flags are opt-in; the default response is unchanged


def test_missing_map_matches_column_counts(client):
    rows = [["a", "b"]] + [[i if i % 4 else None, "x" if i < 150 else None] for i in range(200)]
    sid = _session(client, fx.xlsx_from_rows(rows), "m.xlsx")
    p = client.get(f"/api/sessions/{sid}/profile").json()
    mm = p["missing_map"]
    assert mm["buckets"] == 50 and mm["bucket_rows"] == 4 and mm["columns"] == ["a", "b"]
    for name, values in zip(mm["columns"], mm["values"], strict=True):
        col = next(c for c in p["column_profiles"] if c["name"] == name)
        assert round(sum(v * mm["bucket_rows"] for v in values)) == col["missing"]
    assert mm["values"][1][:37] == [0.0] * 37 and mm["values"][1][38:] == [1.0] * 12


@pytest.mark.parametrize("path", ["issues/Q01:*/rows", "rows?flags=true"])
def test_other_workspaces_cannot_drill_down(client, other_client, path):
    sid = _session(client)
    other_client.get("/api/settings")
    assert other_client.get(f"/api/sessions/{sid}/{path}").status_code == 404
