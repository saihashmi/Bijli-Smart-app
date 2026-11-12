"""Run Alembic migrations programmatically (used at startup and in tests)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from .db import engine

BACKEND_DIR = Path(__file__).resolve().parents[1]


def upgrade_to_head() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["configure_logger"] = False
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
