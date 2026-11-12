"""Configuration from environment variables. Defaults match SPEC.md (D1–D5)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _bool(name: str, default: bool) -> bool:
    return _env(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    app_version: str = "0.1.0"
    storage_dir: Path = field(default_factory=lambda: Path(_env("STORAGE_DIR", "./storage")).resolve())
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", ""))
    # Limits (SPEC D4)
    max_upload_mb: int = field(default_factory=lambda: int(_env("MAX_UPLOAD_MB", "20")))
    retention_days: int = field(default_factory=lambda: int(_env("RETENTION_DAYS", "7")))
    process_timeout_s: int = field(default_factory=lambda: int(_env("PROCESS_TIMEOUT_S", "60")))
    worker_memory_mb: int = field(default_factory=lambda: int(_env("WORKER_MEMORY_MB", "2048")))
    max_rows: int = field(default_factory=lambda: int(_env("MAX_ROWS", "1000000")))
    max_columns: int = field(default_factory=lambda: int(_env("MAX_COLUMNS", "500")))
    max_cells: int = field(default_factory=lambda: int(_env("MAX_CELLS", "20000000")))
    # Zip-bomb guards for .xlsx (an xlsx is a zip archive)
    max_uncompressed_mb: int = field(default_factory=lambda: int(_env("MAX_UNCOMPRESSED_MB", "300")))
    max_zip_entries: int = field(default_factory=lambda: int(_env("MAX_ZIP_ENTRIES", "10000")))
    # Display
    display_timezone: str = field(default_factory=lambda: _env("DISPLAY_TIMEZONE", "Asia/Karachi"))
    # Security
    cors_origins: list[str] = field(default_factory=lambda: _list(_env("CORS_ORIGINS", "")))
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY", ""))
    cookie_secure: bool = field(default_factory=lambda: _bool("COOKIE_SECURE", False))
    rate_limits_enabled: bool = field(default_factory=lambda: _bool("RATE_LIMITS_ENABLED", True))
    # Optional AI (SPEC D5)
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: _env("GROQ_MODEL", "llama-3.3-70b-versatile"))

    workspace_cookie: str = "dd_workspace"

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.storage_dir / 'datadoctor.db'}"

    @property
    def ai_configured(self) -> bool:
        return bool(self.groq_api_key)


settings = Settings()
