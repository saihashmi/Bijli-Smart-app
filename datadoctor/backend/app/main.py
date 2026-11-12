"""DataDoctor AI API. Milestone 1 skeleton: a single health endpoint (full health checks arrive in M3)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

app = FastAPI(
    title="DataDoctor AI API",
    version=settings.app_version,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

if settings.cors_origins:  # same-origin via the Next.js proxy by default; CORS only if configured
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )


@app.get("/api/health", tags=["health"])
def health() -> dict[str, object]:
    return {"status": "ok", "version": settings.app_version, "ai_configured": settings.ai_configured}
