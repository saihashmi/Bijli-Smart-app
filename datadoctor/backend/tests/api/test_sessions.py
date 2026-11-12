from datetime import timedelta

from app.db import SessionLocal
from app.models import AnalysisSession, Dataset, utcnow
from app.services.storage.paths import safe_path
from app.services.storage.retention import purge_expired
from tests.fixtures import builders as fx


def _upload(client, name="sales.xlsx", data=None):
    res = client.post("/api/uploads", files={"file": (name, data or fx.xlsx_multi_sheet())})
    assert res.status_code == 201, res.text
    return res.json()


def test_peek_shows_raw_rows_including_title_row(client):
    ds = _upload(client)
    peek = client.get(f"/api/datasets/{ds['id']}/sheets/0/peek?rows=4").json()
    assert peek["rows"][0][0] == "Monthly sales report"
    assert peek["rows"][1] == ["Date", "City", "Amount (PKR)", "Doubled"]
    assert peek["rows"][2][:3] == ["2026-04-03", "Lahore", "1250.5"]
    assert peek["rows"][3][:3] == ["03/04/2026", " lahore", "Rs 1,000"]  # raw values untouched
    assert peek["total_rows"] == 5


def test_peek_hidden_sheet_and_unknown_sheet(client):
    ds = _upload(client)
    assert client.get(f"/api/datasets/{ds['id']}/sheets/1/peek").json()["rows"][0] == ["Code", "Name"]
    res = client.get(f"/api/datasets/{ds['id']}/sheets/99/peek")
    assert res.status_code == 404 and res.json()["error"]["code"] == "SHEET_NOT_FOUND"


def test_create_session_with_header_row_and_list_it(client):
    ds = _upload(client)
    res = client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0, "header_row": 1})
    assert res.status_code == 201, res.text
    sess = res.json()
    # rows = data rows below the header row (5 sheet rows - title - header)
    assert (sess["sheet_name"], sess["header_row"], sess["rows"], sess["columns"]) == ("Sales", 1, 3, 4)
    listed = client.get("/api/sessions").json()
    assert [s["id"] for s in listed] == [sess["id"]]
    detail = client.get(f"/api/datasets/{ds['id']}").json()
    assert detail["sessions"][0]["id"] == sess["id"]


def test_session_validation(client):
    ds = _upload(client)
    bad = [
        ({"sheet_index": 3}, "SHEET_NOT_USABLE"),  # empty sheet
        ({"sheet_index": 4}, "SHEET_NOT_FOUND"),  # chart sheets are not offered as tables
        ({"sheet_index": 9}, "SHEET_NOT_FOUND"),
        ({"sheet_index": 0, "header_row": 5}, "INVALID_HEADER_ROW"),
        ({"sheet_index": 0, "header_row": -1}, "INVALID_INPUT"),
    ]
    for body, code in bad:
        res = client.post(f"/api/datasets/{ds['id']}/sessions", json=body)
        assert res.json()["error"]["code"] == code, body


def test_other_workspaces_cannot_see_or_touch_data(client, other_client):
    ds = _upload(client)
    sess = client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0}).json()
    other_client.get("/api/settings")  # gets its own workspace
    for method, url in [
        ("get", f"/api/datasets/{ds['id']}"),
        ("get", f"/api/datasets/{ds['id']}/sheets/0/peek"),
        ("delete", f"/api/datasets/{ds['id']}"),
        ("get", f"/api/sessions/{sess['id']}"),
        ("delete", f"/api/sessions/{sess['id']}"),
    ]:
        res = getattr(other_client, method)(url)
        assert res.status_code == 404, (method, url)
    assert other_client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0}).status_code == 404
    assert other_client.get("/api/datasets").json() == []
    assert other_client.get("/api/sessions").json() == []
    assert client.get(f"/api/datasets/{ds['id']}").status_code == 200  # still intact for the owner


def test_delete_dataset_removes_original_and_sessions(client):
    ds = _upload(client)
    client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0})
    stored = safe_path("originals", f"{ds['id']}.xlsx")
    assert stored.exists()
    assert client.delete(f"/api/datasets/{ds['id']}").status_code == 204
    assert not stored.exists()
    assert client.get(f"/api/datasets/{ds['id']}").status_code == 404
    assert client.get("/api/sessions").json() == []


def test_delete_session_keeps_dataset(client):
    ds = _upload(client)
    sess = client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0}).json()
    assert client.delete(f"/api/sessions/{sess['id']}").status_code == 204
    assert client.get(f"/api/sessions/{sess['id']}").status_code == 404
    assert client.get(f"/api/datasets/{ds['id']}").json()["sessions"] == []


def test_retention_purges_expired_datasets(client):
    ds = _upload(client)
    sess = client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0}).json()
    keep = _upload(client, "keep.csv", fx.csv_bytes())
    with SessionLocal() as db:
        db.get(Dataset, ds["id"]).expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
        assert purge_expired(db) == 1
        assert db.get(Dataset, ds["id"]).status == "deleted"
        assert db.get(AnalysisSession, sess["id"]).status == "expired"
    assert not safe_path("originals", f"{ds['id']}.xlsx").exists()
    assert safe_path("originals", f"{keep['id']}.csv").exists()
    assert [d["id"] for d in client.get("/api/datasets").json()] == [keep["id"]]
    assert client.get(f"/api/sessions/{sess['id']}").status_code == 404


def test_upload_rate_limit(client):
    codes = [client.post("/api/uploads", files={"file": ("a.csv", fx.csv_bytes())}).status_code for _ in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429
