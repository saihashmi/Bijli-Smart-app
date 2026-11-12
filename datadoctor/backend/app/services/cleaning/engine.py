"""Validate, run, preview and apply cleaning operations. Preview and apply run in the worker process."""

from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import ValidationError

from ...errors import AppError
from ..ingest.workbook import display_value
from ..storage import snapshots
from .ops import OpError, OpResult, _same
from .registry import REGISTRY

SAMPLE_ROWS = 8


def validate(op_type: str, parameters: dict[str, Any]):
    spec = REGISTRY.get(op_type)
    if spec is None:
        raise AppError(422, "UNKNOWN_OPERATION", f"Unknown cleaning operation “{op_type}”.")
    try:
        return spec, spec.model.model_validate(parameters or {})
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(x) for x in err['loc']) or 'parameters'}: {err['msg']}" for err in e.errors()[:5]
        )
        raise AppError(422, "INVALID_PARAMETERS", problems) from e


def run(df: pd.DataFrame, op_type: str, parameters: dict[str, Any], ctx: dict[str, Any]) -> tuple[Any, Any, OpResult]:
    spec, p = validate(op_type, parameters)
    try:
        result = spec.fn(df, p, ctx)
    except OpError as e:
        raise AppError(422, "INVALID_OPERATION", str(e)) from e
    return spec, p, result


def _cell(v: Any) -> str | None:
    return None if v is None else display_value(v)


def preview_payload(before: pd.DataFrame, spec, p, result: OpResult, header_row: int) -> dict[str, Any]:
    labels = list(result.changed[:SAMPLE_ROWS])
    after = result.df
    cols_before = [c for c in result.focus if c in before.columns]
    cols_after = [result.renamed.get(c, c) for c in result.focus]
    cols_after = [c for c in cols_after if c in after.columns]
    if not labels and result.renamed:  # column-level change: show the first rows
        labels = list(before.index[:SAMPLE_ROWS])
        cols_before = list(result.renamed)
    sample = []
    for label in labels:
        row_before = {c: _cell(before.at[label, c]) for c in cols_before} if label in before.index else {}
        removed = label not in after.index
        row_after = {} if removed else {c: _cell(after.at[label, c]) for c in cols_after}
        # Same text on screen but a different stored value: the cell's type changed (e.g. text → real date).
        converted = [
            c
            for c in cols_after
            if not removed
            and c in before.columns
            and row_before.get(c) == row_after.get(c)
            and not _same(before.at[label, c], after.at[label, c])
        ]
        sample.append(
            {
                "row": int(label) + header_row + 2,
                "before": row_before,
                "after": row_after,
                "removed": removed,
                "converted": converted,
            }
        )
    return {
        "operation_type": spec.id,
        "title": spec.title,
        "parameters": p.model_dump(),
        "destructive": bool(spec.destructive(p)),
        "affected_rows": result.affected_rows,
        "rows_before": int(len(before)),
        "rows_after": int(len(after)),
        "removed_rows": result.removed_rows,
        "added_columns": result.added_columns,
        "removed_columns": result.removed_columns,
        "renamed": result.renamed,
        "summary": result.summary,
        "warnings": result.warnings,
        "failure_count": result.failure_count,
        "failures": [{**f, "row": f["row"] + header_row + 2} for f in result.failures],
        "columns_before": cols_before,
        "columns_after": cols_after,
        "sample": sample,
        "date_rule": list(result.date_rule) if result.date_rule else None,
    }


# ---------- worker entry points ----------


def preview_task(dataset_id: str, session_id: str, version: int, op_type: str, parameters: dict, ctx: dict) -> dict:
    df = snapshots.load(dataset_id, session_id, version)
    spec, p, result = run(df, op_type, parameters, ctx)
    return preview_payload(df, spec, p, result, ctx.get("header_row", 0))


def apply_task(
    dataset_id: str, session_id: str, version: int, new_version: int, op_type: str, parameters: dict, ctx: dict
) -> dict:
    df = snapshots.load(dataset_id, session_id, version)
    spec, p, result = run(df, op_type, parameters, ctx)
    payload = preview_payload(df, spec, p, result, ctx.get("header_row", 0))
    if result.affected_rows == 0:
        return payload  # nothing written; the caller reports "nothing to change"
    base = snapshots.read_meta(dataset_id, session_id, 0) or {}
    meta = {
        **{k: base.get(k) for k in ("header_row", "header_changes", "warnings", "merged_ranges", "excel_error_cells")},
        "version": new_version,
        "rows": int(len(result.df)),
        "columns": [str(c) for c in result.df.columns],
        "operation": {
            "type": op_type,
            "parameters": payload["parameters"],
            "summary": result.summary,
            "failure_count": result.failure_count,
            "failures": payload["failures"],
        },
    }
    snapshots.write(result.df, meta, dataset_id, session_id, new_version)
    return payload
