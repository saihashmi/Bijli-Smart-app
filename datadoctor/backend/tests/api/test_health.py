from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_ok_and_ai_off():
    with TestClient(app) as client:
        res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["ai_configured"] is False


def test_openapi_schema_available():
    with TestClient(app) as client:
        assert client.get("/api/openapi.json").status_code == 200
