from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ..config import settings
from ..db import engine
from ..services.storage.paths import storage_writable

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    """Liveness + dependency checks. Returns 503 if the database or storage is unusable. Contains no user data."""
    checks = {"database": "ok", "storage": "ok"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - report as a failed check, details stay in the server log
        checks["database"] = "error"
    if not storage_writable():
        checks["storage"] = "error"
    ok = all(v == "ok" for v in checks.values())
    body = {
        "status": "ok" if ok else "degraded",
        "version": settings.app_version,
        "ai_configured": settings.ai_configured,
        "checks": checks,
    }
    return JSONResponse(body, status_code=200 if ok else 503)
