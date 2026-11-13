"""Worker entry point for exports (module-level so the spawned process can import it)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..storage import snapshots
from .excel import build_xlsx
from .pdf import build_pdf


def export_task(
    kind: str, dataset_id: str, session_id: str, version: int, ctx: dict[str, Any], out: str
) -> dict[str, Any]:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    try:
        if kind == "xlsx":
            info = build_xlsx(snapshots.load(dataset_id, session_id, version), ctx, tmp)
        else:
            info = build_pdf(ctx, tmp)
        tmp.replace(path)
        return info
    finally:
        tmp.unlink(missing_ok=True)
