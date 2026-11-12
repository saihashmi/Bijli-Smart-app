"""File storage for raw and cleaned frames (pickled DataFrames written only by this app)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import settings


def raw_frame_path(dataset_id: str) -> Path:
    return settings.processed_dir / f"{dataset_id}.raw.pkl"


def clean_frame_path(dataset_id: str) -> Path:
    return settings.processed_dir / f"{dataset_id}.clean.pkl"


def save(df: pd.DataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return str(path)


def load(path: str | Path) -> pd.DataFrame:
    return pd.read_pickle(path)


def remove(*paths: str | Path | None) -> None:
    for p in paths:
        if p:
            Path(p).unlink(missing_ok=True)
