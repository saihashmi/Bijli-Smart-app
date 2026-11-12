from datetime import UTC, datetime

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Dataset
from app.security import unsign
from app.services.storage.paths import safe_path


def test_defaults_match_spec(client):
    body = client.get("/api/settings").json()
    assert body["preferences"] == {
        "display_timezone": "Asia/Karachi",
        "date_display": "DD/MM/YYYY",
        "ai_share_column_names": True,
    }
    system = body["system"]
    assert system["local_mode"] is True
    assert system["retention_days"] == 7
    assert system["max_upload_mb"] == 20
    assert system["ai_configured"] is False and system["ai_model"] is None


def test_update_preferences(client):
    res = client.put("/api/settings", json={"display_timezone": "Asia/Dubai", "ai_share_column_names": False})
    assert res.status_code == 200
    prefs = res.json()["preferences"]
    assert prefs["display_timezone"] == "Asia/Dubai"
    assert prefs["ai_share_column_names"] is False
    assert prefs["date_display"] == "DD/MM/YYYY"


def test_invalid_input_uses_error_envelope(client):
    res = client.put("/api/settings", json={"display_timezone": "Mars/Olympus"})
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "INVALID_INPUT"
    assert "time zone" in err["message"]
    assert err["id"].startswith("err_")
    assert "Mars/Olympus" not in err["message"]  # submitted values are not echoed


def test_unknown_fields_rejected(client):
    assert client.put("/api/settings", json={"retention_days": 1}).status_code == 422
    assert client.put("/api/settings", json={"date_display": "DD-MM-YY"}).status_code == 422


def test_delete_all_data_removes_records_and_files(client):
    client.get("/api/settings")
    ws_id = unsign(client.cookies.get("dd_workspace"), "workspace")
    original = safe_path("originals", "test-delete.csv")
    original.write_text("a,b\n1,2\n")
    with SessionLocal() as db:
        db.add(
            Dataset(
                workspace_id=ws_id,
                original_filename="t.csv",
                file_type="csv",
                file_size=8,
                sha256="0" * 64,
                storage_reference="test-delete.csv",
                expires_at=datetime.now(UTC),
            )
        )
        db.commit()
    res = client.delete("/api/workspace/data")
    assert res.status_code == 200
    assert res.json() == {"datasets_deleted": 1}
    assert not original.exists()
    with SessionLocal() as db:
        assert db.scalars(select(Dataset).where(Dataset.workspace_id == ws_id)).all() == []
