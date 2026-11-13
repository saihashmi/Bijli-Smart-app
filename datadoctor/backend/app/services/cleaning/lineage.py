"""Column lineage: which original column each current column came from."""

from __future__ import annotations

from typing import Any


def column_origins(active_ops: list[dict[str, Any]], original_columns: list[str]) -> dict[str, str]:
    """current column name → original column name, following active renames and removals.
    `active_ops` = [{"type": ..., "parameters": {...}}, ...] in order."""
    names = {c: c for c in original_columns}  # original → current
    for op in active_ops:
        if op["type"] == "rename_columns":
            mapping = op["parameters"].get("mapping") or {}
            names = {orig: mapping.get(cur, cur) for orig, cur in names.items()}
        elif op["type"] == "remove_columns":
            gone = set(op["parameters"].get("columns") or [])
            names = {orig: cur for orig, cur in names.items() if cur not in gone}
    return {cur: orig for orig, cur in names.items()}
