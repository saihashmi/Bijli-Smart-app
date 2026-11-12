from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MappingIn(BaseModel):
    timestamp: str | None = None
    consumption: str | None = None
    cost: str | None = None
    category: str | None = None
    dayfirst: bool = True


class SettingsIn(BaseModel):
    currency: str = Field(default="Rs", max_length=8)
    tariff_per_kwh: float | None = Field(default=None, ge=0)
    peak_start_hour: int = Field(default=18, ge=0, le=23)
    peak_end_hour: int = Field(default=22, ge=0, le=24)
    reduction_target_pct: float = Field(default=10, gt=0, le=90)


class ConfigIn(BaseModel):
    mapping: MappingIn | None = None
    settings: SettingsIn | None = None
    name: str | None = Field(default=None, max_length=255)


class CleanIn(BaseModel):
    actions: list[str]


class JobOut(BaseModel):
    id: int
    dataset_id: str | None
    kind: str
    status: str
    message: str
    details: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class DatasetOut(BaseModel):
    id: str
    name: str
    original_filename: str
    file_type: str
    status: str
    rows_raw: int
    rows_clean: int | None
    columns: list[str]
    mapping: dict[str, Any]
    settings: dict[str, Any]
    cleaning_log: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
