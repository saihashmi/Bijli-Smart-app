"""Worker entry points (must stay module-level so the spawned process can import them)."""

from __future__ import annotations

from typing import Any

from ..storage import snapshots
from .profile import dataset_profile

PROFILE_SCHEMA = "4"  # bump when the shape of stored profiles changes, so old cached profiles are recomputed


def profile_snapshot(dataset_id: str, session_id: str, version: int, context: dict[str, Any] | None = None) -> dict:
    df = snapshots.load(dataset_id, session_id, version)
    return dataset_profile(df, context=context)
