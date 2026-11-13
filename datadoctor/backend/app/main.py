"""DataDoctor AI API."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .errors import install_error_handlers
from .middleware.upload_limit import UploadSizeLimitMiddleware
from .migrate import upgrade_to_head
from .routers import analyst, analytics, cleaning, datasets, exports, health, sessions
from .routers import settings as settings_router
from .security import secret_key
from .services.storage.paths import ensure_storage
from .services.storage.retention import retention_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_storage()
    secret_key()
    upgrade_to_head()
    task = asyncio.create_task(retention_loop())  # runs now, then hourly
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="DataDoctor AI API",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
install_error_handlers(app)
app.add_middleware(UploadSizeLimitMiddleware)

if settings.cors_origins:  # same-origin via the Next.js proxy by default; CORS only if configured
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
        allow_credentials=True,
    )

app.include_router(health.router)
app.include_router(settings_router.router)
app.include_router(datasets.router)
app.include_router(sessions.router)
app.include_router(cleaning.router)
app.include_router(analytics.router)
app.include_router(analyst.router)
app.include_router(exports.router)
