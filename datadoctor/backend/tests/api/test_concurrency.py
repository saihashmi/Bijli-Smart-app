"""Regression (Milestone 5): slow work must not hold the SQLite write lock and block other requests."""

import threading
import time

from fastapi.testclient import TestClient

from app.main import app
from app.routers import sessions as sessions_router
from tests.fixtures import builders as fx
from tests.unit import worker_tasks


def test_upload_succeeds_while_another_session_is_being_parsed(monkeypatch):
    monkeypatch.setattr(sessions_router, "parse_to_snapshot", worker_tasks.slow_parse)
    with TestClient(app) as a, TestClient(app) as b:
        ds = a.post("/api/uploads", files={"file": ("a.xlsx", fx.xlsx_simple())}).json()
        result = {}

        def create():
            result["res"] = a.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0})

        t = threading.Thread(target=create)
        t.start()
        time.sleep(1.5)  # the slow parse is now running
        start = time.monotonic()
        res = b.post("/api/uploads", files={"file": ("b.csv", fx.csv_bytes())})
        elapsed = time.monotonic() - start
        t.join(30)
        assert res.status_code == 201, res.text
        assert elapsed < 4, f"upload waited {elapsed:.1f}s for a lock"
        assert result["res"].status_code == 201, result["res"].text
