from __future__ import annotations

from typing import Literal
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator

DateDisplay = Literal["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"]
_ZONES = available_timezones()


def _check_zone(v: str | None) -> str | None:
    if v is not None and v not in _ZONES:
        raise ValueError("unknown time zone")
    return v


class Preferences(BaseModel):
    """Per-workspace preferences (stored in workspaces.settings_json)."""

    display_timezone: str = "Asia/Karachi"
    date_display: DateDisplay = "DD/MM/YYYY"
    ai_share_column_names: bool = Field(
        default=True, description="Send column names to the AI provider (otherwise anonymised aliases are used)."
    )

    _zone = field_validator("display_timezone")(_check_zone)


class PreferencesUpdate(BaseModel):
    display_timezone: str | None = None
    date_display: DateDisplay | None = None
    ai_share_column_names: bool | None = None

    model_config = {"extra": "forbid"}

    _zone = field_validator("display_timezone")(_check_zone)


class SystemInfo(BaseModel):
    version: str
    local_mode: bool
    retention_days: int
    max_upload_mb: int
    max_rows: int
    max_columns: int
    max_cells: int
    process_timeout_s: int
    ai_configured: bool
    ai_provider: str | None
    ai_model: str | None


class SettingsOut(BaseModel):
    preferences: Preferences
    system: SystemInfo


class DeleteAllOut(BaseModel):
    datasets_deleted: int
