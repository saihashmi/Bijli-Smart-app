from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import AppError, install_error_handlers


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret cell value 4111-1111")

    @app.get("/expected")
    def expected():
        raise AppError(409, "CONFLICT", "Resolve ambiguous dates first.")

    return app


def test_unexpected_errors_hide_details():
    with TestClient(_app(), raise_server_exceptions=False) as c:
        res = c.get("/boom")
    assert res.status_code == 500
    body = res.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in res.text and "Traceback" not in res.text


def test_app_errors_keep_code_and_message():
    with TestClient(_app()) as c:
        res = c.get("/expected")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CONFLICT"


def test_unknown_route_uses_envelope():
    with TestClient(_app()) as c:
        res = c.get("/nope")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
