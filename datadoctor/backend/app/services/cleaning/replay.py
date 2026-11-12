"""Rebuild any version deterministically: original snapshot (v0) + the active operations, replayed in order.

Disk policy: v0 and the most recent KEEP_RECENT active versions are kept as files; older ones are deleted
(their small .meta.json files stay, for the history). A missing version is rebuilt from the nearest kept one.
"""

from __future__ import annotations

from typing import Any

from ..storage import snapshots
from ..storage.paths import remove
from .engine import run

KEEP_RECENT = 3


def materialize_task(
    dataset_id: str, session_id: str, target: int, chain: list[dict[str, Any]], ctx: dict[str, Any]
) -> dict[str, Any]:
    """Worker entry point. `chain` = active operations with sequence ≤ target, in order:
    [{"seq": 1, "type": "trim_whitespace", "parameters": {...}}, ...]."""
    if target == 0 or snapshots.exists(dataset_id, session_id, target):
        return {"rebuilt": False, "replayed": 0}
    # Start from the latest kept snapshot inside the chain, else the original.
    start_idx, df = -1, None
    for i in range(len(chain) - 1, -1, -1):
        if snapshots.exists(dataset_id, session_id, chain[i]["seq"]):
            start_idx, df = i, snapshots.load(dataset_id, session_id, chain[i]["seq"])
            break
    if df is None:
        df = snapshots.load(dataset_id, session_id, 0)
    replayed = 0
    for step in chain[start_idx + 1 :]:
        _, _, result = run(df, step["type"], step["parameters"], ctx)
        df = result.df
        replayed += 1
    meta = snapshots.read_meta(dataset_id, session_id, target) or {}
    meta.update(version=target, rows=int(len(df)), columns=[str(c) for c in df.columns])
    snapshots.write(df, meta, dataset_id, session_id, target)
    return {"rebuilt": True, "replayed": replayed}


def prune(dataset_id: str, session_id: str, active_seqs: list[int]) -> list[int]:
    """Delete snapshot data files except v0 and the newest KEEP_RECENT active versions. Returns deleted versions."""
    keep = {0, *sorted(active_seqs)[-KEEP_RECENT:]}
    folder = snapshots.snapshot_dir(dataset_id, session_id)
    deleted = []
    if not folder.exists():
        return deleted
    for f in folder.glob("v*.pkl"):
        try:
            v = int(f.stem[1:])
        except ValueError:
            continue
        if v not in keep:
            remove(f)
            deleted.append(v)
    snapshots.forget(str(folder))
    return sorted(deleted)
