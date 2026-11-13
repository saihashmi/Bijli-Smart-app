"""M13: Excel and PDF exports. Contents are read back and compared with the data and the analytics engine."""

import datetime as dt
import io
import re
import time

from openpyxl import load_workbook

from app.security import sign
from tests.fixtures import builders as fx


def _workbook() -> bytes:
    rows = [["Order", "Date", "Region", "Units", "Amount", "Note"]]
    notes = ["@HYPERLINK(1)", "+1+1", "-2", "@SUM(A1)", "\tTabbed", "plain text", None]
    for i in range(40):
        amount = None if i in (5, 15) else 100 * (i % 5 + 1)
        rows.append(
            [
                f"O-{i + 1}",
                dt.date(2026, 1 + (i % 3), 1 + (i % 20)),
                ["North", "South"][i % 2],
                (i % 7) + 1,
                amount,
                notes[i % 7],
            ]
        )
    rows.append(list(rows[1]))  # one exact duplicate
    return fx.xlsx_from_rows(rows, title="Sales")


def _session(client):
    ds = client.post("/api/uploads", files={"file": ("sales report.xlsx", _workbook())}).json()
    return client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0}).json()["id"]


def _export(client, sid, kind, **extra):
    res = client.post(f"/api/sessions/{sid}/exports", json={"type": kind, **extra})
    assert res.status_code == 201, res.text
    job = res.json()
    assert job["status"] == "done", job
    return job


def test_excel_export_has_four_sheets_with_cleaned_data_and_safe_text(client):
    sid = _session(client)
    res = client.post(
        f"/api/sessions/{sid}/cleaning/apply",
        json={"operation_type": "remove_exact_duplicates", "parameters": {}, "confirm": True},
    )
    assert res.status_code == 200, res.text
    job = _export(client, sid, "xlsx")
    assert job["file_name"] == "sales report - cleaned.xlsx" and job["details"]["rows"] == 40

    file = client.get(job["download_url"])
    assert file.status_code == 200
    assert "sales%20report%20-%20cleaned.xlsx" in file.headers["content-disposition"]
    assert file.headers["cache-control"] == "no-store"
    wb = load_workbook(io.BytesIO(file.content))
    assert wb.sheetnames == ["Cleaned Data", "Data Quality Report", "Cleaning Audit Log", "Summary Statistics"]

    data = wb["Cleaned Data"]
    assert [c.value for c in data[1]] == ["Order", "Date", "Region", "Units", "Amount", "Note"]
    assert data.max_row == 41 and data.freeze_panes == "A2" and data.auto_filter.ref == "A1:F41"
    assert data[1][0].font.bold
    # native types survive; missing stays empty (never 0)
    assert data["D2"].value == 1 and isinstance(data["B2"].value, dt.datetime) and data["E7"].value is None
    amounts = [r[4].value for r in data.iter_rows(min_row=2)]
    assert sum(a for a in amounts if a is not None) == sum(100 * (i % 5 + 1) for i in range(40) if i not in (5, 15))
    # formula injection: nothing is a formula, dangerous text is prefixed
    notes = [r[5].value for r in data.iter_rows(min_row=2)]
    assert notes[:7] == [
        "'@HYPERLINK(1)",
        "'+1+1",
        "'-2",
        "'@SUM(A1)",
        "'\tTabbed",
        "plain text",
        None,
    ]
    assert all(c.data_type != "f" for row in data.iter_rows() for c in row)
    assert job["details"]["neutralised_cells"] == sum(1 for n in notes if n and n.startswith("'"))

    quality = [[c.value for c in r] for r in wb["Data Quality Report"].iter_rows()]
    profile = client.get(f"/api/sessions/{sid}/profile").json()
    score_row = next(r for r in quality if r[0] == "Data Health Score")
    assert score_row[1] == profile["health"]["score"]  # same figure as the app
    assert re.search(r"Generated \d{2} \w{3} \d{4} \d{2}:\d{2} PKT \(Asia/Karachi\)", quality[1][0])
    listed = {(r[0], r[1]) for r in quality if r[3] in ("high", "medium", "low")}
    assert listed == {(i["title"], i["column"] or "(whole sheet)") for i in profile["issues"]}

    audit = [[c.value for c in r] for r in wb["Cleaning Audit Log"].iter_rows()]
    assert audit[-1][:5] == [1, "Remove exact duplicate rows", '{"keep": "first"}', 1, "applied"]

    stats = {r[0].value: r for r in wb["Summary Statistics"].iter_rows(min_row=5)}
    assert stats["Amount"][2].value == 38 and stats["Amount"][3].value == 2
    assert stats["Amount"][8].value == profile["column_profiles"][4]["numeric"]["mean"]


def test_pdf_report_contains_the_same_figures_as_the_app(client):
    from pypdf import PdfReader

    sid = _session(client)
    widgets = [
        {
            "id": "k",
            "title": "Total amount",
            "chart": "kpi",
            "query": {"kind": "aggregate", "measure": {"agg": "sum", "column": "Amount"}},
        },
        {
            "id": "b",
            "title": "Amount by region",
            "chart": "bar",
            "query": {
                "kind": "aggregate",
                "measure": {"agg": "sum", "column": "Amount"},
                "dimension": {"column": "Region"},
            },
        },
        {
            "id": "s",
            "title": "Units vs amount",
            "chart": "scatter",
            "query": {"kind": "scatter", "x": "Units", "y": "Amount"},
        },
    ]
    assert (
        client.put(
            f"/api/sessions/{sid}/dashboard", json={"theme": "executive", "filters": [], "widgets": widgets}
        ).status_code
        == 200
    )
    client.post(f"/api/sessions/{sid}/analyst/ask", json={"question": "How many rows are there?"})
    job = _export(client, sid, "pdf")
    assert (
        job["file_name"] == "sales report - report.pdf"
        and job["details"]["pages"] >= 2
        and job["details"]["charts"] == 1
    )

    file = client.get(job["download_url"])
    assert (
        file.status_code == 200 and file.content[:5] == b"%PDF-" and file.headers["content-type"] == "application/pdf"
    )
    text = " ".join(" ".join((page.extract_text() or "").split()) for page in PdfReader(io.BytesIO(file.content)).pages)
    profile = client.get(f"/api/sessions/{sid}/profile").json()
    total = client.post(f"/api/sessions/{sid}/analytics/query", json={"queries": [widgets[0]["query"]]}).json()[
        "results"
    ][0]["result"]["total"]["value"]
    assert f"{profile['health']['score']} out of 100" in text
    assert "Dataset summary" in text and "Data-quality findings" in text and "Cleaning summary" in text
    assert "No cleaning steps were applied" in text
    assert f"{total:,}" in text and "Amount by region" in text  # dashboard figures from the same engine
    assert "Not drawn in this report" in text and "Units vs amount" in text
    assert "There are 41 rows." in text and "not AI-written" in text
    assert re.search(r"generated \d{2} \w{3} \d{4} \d{2}:\d{2} PKT", text)
    for issue in profile["issues"]:
        assert issue["title"] in text


def test_download_needs_the_owner_and_a_valid_unexpired_link(client, other_client):
    sid = _session(client)
    job = _export(client, sid, "xlsx")
    url = job["download_url"]
    assert other_client.get(url).status_code == 404  # another workspace, even with a valid link
    assert client.get(f"/api/exports/{job['id']}/download?token=forged.abc").status_code == 403
    expired = sign(f"{job['id']}:{int(time.time()) - 5}", "export")
    res = client.get(f"/api/exports/{job['id']}/download?token={expired}")
    assert res.status_code == 403 and res.json()["error"]["code"] == "LINK_EXPIRED"
    other_job = _export(client, sid, "pdf")
    assert client.get(url.replace(job["id"], other_job["id"])).status_code == 403  # a link is tied to one export
    assert client.get("/api/exports/00000000-0000-4000-8000-000000000000/download?token=x.y").status_code == 404

    listed = client.get(f"/api/sessions/{sid}/exports").json()["exports"]
    assert [e["type"] for e in listed] == ["pdf", "xlsx"] and all(e["download_url"] for e in listed)
    assert other_client.get(f"/api/sessions/{sid}/exports").status_code == 404
    assert other_client.delete(f"/api/exports/{job['id']}").status_code == 404
    assert client.delete(f"/api/exports/{job['id']}").status_code == 204
    assert client.get(url).status_code == 404
    assert client.post(f"/api/sessions/{sid}/exports", json={"type": "docx"}).status_code == 422


def test_exports_expire_after_24_hours_and_go_with_the_dataset(client):
    from datetime import timedelta

    from app.db import SessionLocal
    from app.models import ExportJob, utcnow
    from app.services.storage.paths import safe_path
    from app.services.storage.retention import purge_exports

    sid = _session(client)
    job = _export(client, sid, "xlsx")
    with SessionLocal() as db:
        row = db.get(ExportJob, job["id"])
        dataset_id, _, name = row.storage_reference.partition("/")
        path = safe_path("exports", dataset_id, name)
        assert path.exists()
        row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
        assert purge_exports(db) == 1
    assert not path.exists()
    listed = client.get(f"/api/sessions/{sid}/exports").json()["exports"][0]
    assert listed["status"] == "expired" and listed["download_url"] is None
    assert client.get(job["download_url"]).status_code == 410

    second = _export(client, sid, "pdf")
    with SessionLocal() as db:
        dataset_id, _, name = db.get(ExportJob, second["id"]).storage_reference.partition("/")
    assert safe_path("exports", dataset_id, name).exists()
    assert client.delete(f"/api/datasets/{dataset_id}").status_code == 204
    assert not safe_path("exports", dataset_id, name).exists()


def test_timeline_records_exports(client):
    sid = _session(client)
    _export(client, sid, "xlsx")
    events = client.get(f"/api/sessions/{sid}/timeline").json()["events"]
    assert any(e["type"] == "export" and e["details"]["type"] == "xlsx" for e in events)


def test_safe_text_neutralises_every_dangerous_start():
    from app.services.reports.excel import safe_cell, safe_text

    for start in ("=", "+", "-", "@", "\t", "\r"):
        assert safe_text(f"{start}cmd|' /C calc'!A0") == f"'{start}cmd|' /C calc'!A0"
    assert safe_text("normal = text") == "normal = text"
    assert safe_text("bell\x07char") == "bellchar"  # control characters cannot be stored in a workbook
    assert safe_cell(-5) == -5 and safe_cell(float("nan")) is None and safe_cell(None) is None  # numbers stay numbers
