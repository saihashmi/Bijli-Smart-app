import openpyxl
import pytest

from tests.fixtures import builders as fx


def _session(client, data, name="invoices.xlsx", header_row=0, sheet=0):
    ds = client.post("/api/uploads", files={"file": (name, data)}).json()
    res = client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": sheet, "header_row": header_row})
    assert res.status_code == 201, res.text
    return res.json()


def test_session_creation_parses_sheet_and_reports_header_changes(client):
    sess = _session(client, fx.profiling_workbook())
    assert sess["rows"] == 8  # trailing data rows kept, including one fully empty row in the middle
    assert sess["column_names"] == ["Invoice", "Date", "City", "Amount", "Paid", "Column 6", "Amount (2)", "Notes"]
    reasons = {c["new"]: c["reason"] for c in sess["header_changes"]}
    assert reasons == {"Column 6": "blank", "Amount (2)": "duplicate"}


def test_rows_endpoint_matches_source_cells_exactly(client):
    data = fx.profiling_workbook()
    sess = _session(client, data)
    page = client.get(f"/api/sessions/{sess['id']}/rows?offset=0&limit=500").json()
    ws = openpyxl.load_workbook(__import__("io").BytesIO(data)).active
    source = [list(r) for r in ws.iter_rows(min_row=2, values_only=True)]
    assert page["total"] == len(source)
    for got, want in zip(page["rows"], source, strict=True):
        for g, w in zip(got, want, strict=True):
            excel_error = isinstance(w, str) and w.startswith("#") and w.endswith(("!", "?", "A"))
            if w is None or (isinstance(w, str) and not w.strip()) or excel_error:
                assert g is None  # empty cells, and Excel error cells (the reader returns them as empty)
            elif isinstance(w, float) and w.is_integer():
                assert g == str(int(w))
            elif hasattr(w, "isoformat"):
                assert g.startswith(w.date().isoformat() if hasattr(w, "date") else w.isoformat())
            else:
                assert g == str(w)


def test_rows_paging(client):
    rows = [["n", "sq"]] + [[i, i * i] for i in range(1, 1201)]
    sess = _session(client, fx.xlsx_from_rows(rows), "squares.xlsx")
    page = client.get(f"/api/sessions/{sess['id']}/rows?offset=1000&limit=500").json()
    assert page["total"] == 1200 and len(page["rows"]) == 200
    assert page["rows"][0] == ["1001", str(1001 * 1001)]
    assert client.get(f"/api/sessions/{sess['id']}/rows?limit=501").status_code == 422


def test_trailing_empty_rows_and_columns_are_trimmed(client):
    rows = [["a", "b", None, None], [1, 2, None, None], [3, 4, None, None], [None, None, None, None]]
    sess = _session(client, fx.xlsx_from_rows(rows), "t.xlsx")
    assert (sess["rows"], sess["columns"]) == (2, 2)


def test_excel_error_cells_are_reported(client):
    sess = _session(client, fx.profiling_workbook())
    assert any("1 cell(s) contain Excel errors" in w for w in sess["warnings"])


def test_merged_cells_are_reported(client):
    rows = [["Region", "Q1", "Q2"], ["North", 10, 20], [None, 30, 40]]
    sess = _session(client, fx.xlsx_from_rows(rows, merge="A2:A3"), "m.xlsx")
    assert any("merged cell range" in w for w in sess["warnings"])


def test_header_row_skips_title_rows(client):
    sess = _session(client, fx.xlsx_multi_sheet(), "sales.xlsx", header_row=1)
    assert sess["column_names"] == ["Date", "City", "Amount (PKR)", "Doubled"]
    assert any("1 row(s) above the header row were skipped" in w for w in sess["warnings"])


def test_csv_session(client):
    sess = _session(client, fx.csv_bytes("utf-16", "\t"), "x.csv")
    rows = client.get(f"/api/sessions/{sess['id']}/rows").json()["rows"]
    assert rows == [["Ayesha", "Lahore", "1,250"], ["Bilal", "Karachi", "900"]]


def test_profile_endpoint_counts_and_caching(client):
    sess = _session(client, fx.profiling_workbook())
    first = client.get(f"/api/sessions/{sess['id']}/profile")
    assert first.status_code == 200, first.text
    p = first.json()
    assert (p["rows"], p["columns"]) == (8, 8)
    assert p["duplicate_rows"] == 1  # INV-4 repeated
    assert p["empty_rows"] == 1
    assert p["empty_columns"] == 1  # "Column 6"
    cols = {c["name"]: c for c in p["column_profiles"]}
    # Amount: N/A ×2 (null tokens) + three cells read as empty: the empty row, #DIV/0! (Excel error cells are
    # returned empty by the reader) and "  " (stored without xml:space="preserve", so Excel also sees it as empty).
    assert cols["Amount"]["missing"] == 5
    assert cols["Amount"]["missing_kinds"] == {"empty": 3, "whitespace_only": 0, "null_token": 2, "excel_error": 0}
    assert cols["Date"]["date"]["ambiguous"] == 1
    assert cols["Date"]["date"]["invalid"] == 1
    assert cols["Paid"]["type"] == "boolean"
    assert cols["Notes"]["missing"] == 7
    second = client.get(f"/api/sessions/{sess['id']}/profile").json()
    assert second["calculated_at"] == p["calculated_at"]  # served from cache


@pytest.mark.parametrize("path", ["rows", "profile"])
def test_other_workspaces_cannot_read_rows_or_profile(client, other_client, path):
    sess = _session(client, fx.profiling_workbook())
    other_client.get("/api/settings")
    assert other_client.get(f"/api/sessions/{sess['id']}/{path}").status_code == 404


def test_issue_list_for_known_workbook(client):
    sess = _session(client, fx.profiling_workbook())
    p = client.get(f"/api/sessions/{sess['id']}/profile").json()
    got = {(i["code"], i["column"]): i for i in p["issues"]}
    expected = {
        ("Q01", None): (1, "high"),
        ("Q04", None): (1, "low"),
        ("Q04", "Column 6"): (8, "low"),
        ("Q14", "Column 6"): (8, "low"),
        ("Q14", "Amount (2)"): (8, "low"),
        ("Q03", "Amount"): (5, "high"),
        ("Q03", "Notes"): (7, "high"),
        ("Q03", "City"): (1, "medium"),
        ("Q05", "City"): (1, "medium"),
        ("Q07", "City"): (2, "medium"),
        ("Q08", "Amount"): (2, "medium"),
        ("Q10", "Date"): (4, "medium"),
        ("Q11", "Date"): (1, "high"),
        ("Q12", "Date"): (1, "medium"),
    }
    for key, (affected, severity) in expected.items():
        assert key in got, key
        assert (got[key]["affected_rows"], got[key]["severity"]) == (affected, severity), key
    assert not any(code == "Q16" for code, _ in got)
    assert p["issue_counts"]["high"] == sum(1 for i in p["issues"] if i["severity"] == "high")
    assert p["issues"][0]["severity"] == "high"  # sorted by severity
    h = p["health"]
    assert 0 <= h["score"] <= 100 and h["band"] in {"Excellent", "Good", "Needs attention", "Poor"}
    assert sum(c["points"] for c in h["components"]) == pytest.approx(h["score"], abs=0.5)


def test_mark_sensitive_columns(client):
    data = fx.csv_bytes(
        rows=[
            ["Name", "CNIC", "Amount"],
            ["Ayesha", "35202-1234567-1", "10"],
            ["Bilal", "42101-7654321-3", "20"],
            ["Sana", "61101-1111111-5", "30"],
        ]
    )
    sess = _session(client, data, "people.csv")
    p = client.get(f"/api/sessions/{sess['id']}/profile").json()
    assert {i["column"] for i in p["issues"] if i["code"] == "Q16"} == {"Name", "CNIC"}
    res = client.put(f"/api/sessions/{sess['id']}/sensitive-columns", json={"columns": ["CNIC", "Name"]})
    assert res.json() == {"sensitive_columns": ["Name", "CNIC"]}  # stored in sheet order
    p = client.get(f"/api/sessions/{sess['id']}/profile").json()
    assert not any(i["code"] == "Q16" for i in p["issues"])
    assert p["sensitive_columns"] == ["Name", "CNIC"]
    bad = client.put(f"/api/sessions/{sess['id']}/sensitive-columns", json={"columns": ["Nope"]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "UNKNOWN_COLUMN"

    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import AuditEvent

    with SessionLocal() as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.session_id == sess["id"])).all()
    assert [e.event_type for e in events] == ["sensitive_columns"]
    assert events[0].details_json == {"added": ["Name", "CNIC"], "removed": []}
