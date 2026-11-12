from app.routers import health as health_router


def test_health_reports_ok_and_checks(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "storage": "ok"}
    assert body["ai_configured"] is False


def test_health_returns_503_when_storage_unwritable(client, monkeypatch):
    monkeypatch.setattr(health_router, "storage_writable", lambda: False)
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.json()["checks"]["storage"] == "error"


def test_health_does_not_create_a_workspace(client):
    res = client.get("/api/health")
    assert "dd_workspace" not in res.cookies


def test_openapi_schema_available(client):
    assert client.get("/api/openapi.json").status_code == 200
