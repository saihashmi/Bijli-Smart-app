from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings as cfg
from ..db import get_db
from ..middleware.ratelimit import rate_limit
from ..middleware.workspace import current_workspace
from ..models import Dataset, Workspace
from ..schemas.settings import DeleteAllOut, Preferences, PreferencesUpdate, SettingsOut, SystemInfo
from ..services.storage.paths import remove_dataset_files

router = APIRouter(prefix="/api", tags=["settings"])


def _preferences(ws: Workspace) -> Preferences:
    defaults = Preferences(display_timezone=cfg.display_timezone).model_dump()
    return Preferences(**{**defaults, **(ws.settings_json or {})})


def _system() -> SystemInfo:
    return SystemInfo(
        version=cfg.app_version,
        local_mode=True,
        retention_days=cfg.retention_days,
        max_upload_mb=cfg.max_upload_mb,
        max_rows=cfg.max_rows,
        max_columns=cfg.max_columns,
        max_cells=cfg.max_cells,
        process_timeout_s=cfg.process_timeout_s,
        ai_configured=cfg.ai_configured,
        ai_provider="groq" if cfg.ai_configured else None,
        ai_model=cfg.groq_model if cfg.ai_configured else None,
    )


@router.get("/settings", response_model=SettingsOut)
def get_settings(ws: Workspace = Depends(current_workspace)):
    return SettingsOut(preferences=_preferences(ws), system=_system())


@router.put("/settings", response_model=SettingsOut)
def update_settings(body: PreferencesUpdate, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    merged = {**_preferences(ws).model_dump(), **body.model_dump(exclude_none=True)}
    prefs = Preferences(**merged)  # re-validates the whole object
    ws = db.merge(ws)
    ws.settings_json = prefs.model_dump()
    db.commit()
    return SettingsOut(preferences=prefs, system=_system())


@router.delete("/workspace/data", response_model=DeleteAllOut, dependencies=[Depends(rate_limit("destructive"))])
def delete_all_data(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    """Permanently delete every dataset (files and records) belonging to this workspace."""
    datasets = db.scalars(select(Dataset).where(Dataset.workspace_id == ws.id)).all()
    for ds in datasets:
        remove_dataset_files(ds.id, ds.storage_reference)
        db.delete(ds)
    db.commit()
    return DeleteAllOut(datasets_deleted=len(datasets))
