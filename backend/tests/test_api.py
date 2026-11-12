from fastapi.testclient import TestClient

from app.main import app

from .conftest import SAMPLES


def test_full_flow_csv():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["ai_enabled"] is False
        with open(SAMPLES / "household_hourly_messy.csv", "rb") as fh:
            r = c.post("/api/datasets", files={"file": ("household.csv", fh, "text/csv")})
        assert r.status_code == 201, r.text
        ds = r.json()
        assert ds["mapping"]["timestamp"] == "Reading Time"
        assert ds["mapping"]["consumption"] == "Energy (kWh)"

        prof = c.get(f"/api/datasets/{ds['id']}/profile").json()
        ids = {s["id"] for s in prof["suggestions"]}
        assert {"drop_duplicates", "drop_invalid_dates", "remove_negative", "drop_missing_consumption"} <= ids

        recommended = [s["id"] for s in prof["suggestions"] if s["recommended"]]
        r = c.post(f"/api/datasets/{ds['id']}/clean", json={"actions": recommended})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cleaned"
        assert r.json()["rows_clean"] < ds["rows_raw"]

        prev = c.get(f"/api/datasets/{ds['id']}/preview?stage=clean&limit=5").json()
        assert len(prev["rows"]) == 5

        r = c.patch(f"/api/datasets/{ds['id']}", json={"settings": {"currency": "Rs", "tariff_per_kwh": 50}})
        assert r.status_code == 200

        a = c.get(f"/api/datasets/{ds['id']}/analysis").json()
        assert a["data_stage"] == "cleaned"
        assert a["summary"]["cost_source"] == "tariff"
        assert a["hourly"] and len(a["hourly"]) == 24

        ins = c.post(f"/api/datasets/{ds['id']}/insights").json()
        assert ins["source"] == "rules" and ins["insights"]

        x = c.get(f"/api/datasets/{ds['id']}/export?format=xlsx")
        assert x.status_code == 200 and x.content[:2] == b"PK"
        p = c.get(f"/api/datasets/{ds['id']}/export?format=pdf")
        assert p.status_code == 200 and p.content[:4] == b"%PDF"

        jobs = c.get(f"/api/datasets/{ds['id']}/jobs").json()
        kinds = {j["kind"] for j in jobs}
        assert {"upload", "clean", "analyze", "insights", "export"} <= kinds

        assert c.delete(f"/api/datasets/{ds['id']}").status_code == 204
        assert c.get(f"/api/datasets/{ds['id']}").status_code == 404


def test_excel_bills_use_billed_cost():
    with TestClient(app) as c:
        with open(SAMPLES / "office_monthly_bills.xlsx", "rb") as fh:
            r = c.post("/api/datasets", files={"file": ("bills.xlsx", fh)})
        ds = r.json()
        assert ds["mapping"]["cost"] == "Bill Amount (Rs)"
        assert ds["mapping"]["category"] == "Branch"
        a = c.get(f"/api/datasets/{ds['id']}/analysis").json()
        assert a["data_stage"] == "raw"
        assert a["summary"]["granularity"] == "monthly"
        assert a["summary"]["cost_source"] == "file"
        assert len(a["categories"]) == 3


def test_rejects_bad_uploads():
    with TestClient(app) as c:
        assert c.post("/api/datasets", files={"file": ("x.pdf", b"%PDF")}).status_code == 415
        assert c.post("/api/datasets", files={"file": ("x.csv", b"")}).status_code == 422


def test_mapping_validation():
    with TestClient(app) as c:
        with open(SAMPLES / "household_hourly_messy.csv", "rb") as fh:
            ds = c.post("/api/datasets", files={"file": ("h.csv", fh)}).json()
        r = c.patch(f"/api/datasets/{ds['id']}", json={"mapping": {"timestamp": "Reading Time", "consumption": "Reading Time"}})
        assert r.status_code == 422
