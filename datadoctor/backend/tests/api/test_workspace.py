from datetime import UTC, datetime

import pytest

from app.db import SessionLocal
from app.errors import AppError
from app.middleware.workspace import owned_dataset
from app.models import Dataset, Workspace


def test_first_request_issues_secure_workspace_cookie(client):
    res = client.get("/api/settings")
    assert res.status_code == 200
    header = res.headers["set-cookie"].lower()
    assert "dd_workspace=" in header
    assert "httponly" in header
    assert "samesite=lax" in header


def test_cookie_keeps_the_same_workspace(client):
    client.put("/api/settings", json={"date_display": "YYYY-MM-DD"})
    assert client.get("/api/settings").json()["preferences"]["date_display"] == "YYYY-MM-DD"


def test_workspaces_are_isolated(client, other_client):
    client.put("/api/settings", json={"date_display": "MM/DD/YYYY"})
    assert other_client.get("/api/settings").json()["preferences"]["date_display"] == "DD/MM/YYYY"


def test_tampered_cookie_is_rejected_and_gets_a_fresh_workspace(client):
    client.put("/api/settings", json={"date_display": "MM/DD/YYYY"})
    real = client.cookies.get("dd_workspace")
    workspace_id, _, mac = real.rpartition(".")
    client.cookies.set("dd_workspace", f"{workspace_id}.{'0' * len(mac)}")
    res = client.get("/api/settings")
    assert res.json()["preferences"]["date_display"] == "DD/MM/YYYY"
    assert res.cookies.get("dd_workspace") != real


def _make_dataset(db, ws_id: str) -> Dataset:
    ds = Dataset(
        workspace_id=ws_id,
        original_filename="x.csv",
        file_type="csv",
        file_size=1,
        sha256="0" * 64,
        storage_reference="x.csv",
        expires_at=datetime.now(UTC),
    )
    db.add(ds)
    db.commit()
    return ds


def test_ownership_helper_hides_other_workspaces_data():
    with SessionLocal() as db:
        owner, stranger = Workspace(), Workspace()
        db.add_all([owner, stranger])
        db.commit()
        ds = _make_dataset(db, owner.id)
        assert owned_dataset(db, owner, ds.id).id == ds.id
        with pytest.raises(AppError) as exc:
            owned_dataset(db, stranger, ds.id)
        assert exc.value.status == 404
        with pytest.raises(AppError):
            owned_dataset(db, owner, "does-not-exist")
