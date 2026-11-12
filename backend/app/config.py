"""Runtime configuration, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "./data")).resolve())
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    cors_origins: list[str] = field(
        default_factory=lambda: _list(os.getenv("CORS_ORIGINS", "http://localhost:3000"))
    )
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "25")))
    # Optional AI. When GROQ_API_KEY is empty, insights are produced by deterministic templates only.
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    groq_base_url: str = field(
        default_factory=lambda: os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    )
    groq_timeout_s: float = field(default_factory=lambda: float(os.getenv("GROQ_TIMEOUT_S", "30")))
    default_currency: str = field(default_factory=lambda: os.getenv("DEFAULT_CURRENCY", "Rs"))
    # Day-first date parsing (dd/mm/yyyy) is the common format for bills in South Asia.
    default_dayfirst: bool = field(
        default_factory=lambda: os.getenv("DEFAULT_DAYFIRST", "true").lower() in ("1", "true", "yes")
    )

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'bijli.db'}"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.groq_api_key)


settings = Settings()


def ensure_dirs() -> None:
    for d in (settings.data_dir, settings.upload_dir, settings.processed_dir):
        d.mkdir(parents=True, exist_ok=True)
