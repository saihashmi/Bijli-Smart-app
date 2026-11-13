"""Cleaning Studio API: catalogue, preview (no changes), apply, undo, reset, timeline, before/after comparison.

Current data = original (v0) + active operations replayed in order. Undo marks the last active operation
"undone"; reset marks all of them undone. Nothing is ever deleted from the history.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import AppError
from ..middleware.ratelimit import rate_limit
from ..middleware.workspace import current_workspace, owned_session
from ..models import AnalysisSession, AuditEvent, CleaningOperation, Workspace, utcnow
from ..schemas.datasets import CleaningRequest, OperationOut, ResetRequest
from ..services.cleaning import engine
from ..services.cleaning.lineage import column_origins
from ..services.cleaning.ops import _same, category_suggestions
from ..services.cleaning.registry import REGISTRY, catalogue
from ..services.cleaning.replay import materialize_task, prune
from ..services.ingest.workbook import display_value
from ..services.storage import snapshots
from ..services.storage.paths import remove
from ..worker import run_limited
from .sessions import current_version, session_out

router = APIRouter(prefix="/api", tags=["cleaning"])

# One change at a time per session (single API process; see CLAUDE.md).
_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


def _ctx(sess: AnalysisSession) -> dict[str, Any]:
    return {"header_row": sess.header_row}


def _active(sess: AnalysisSession) -> list[CleaningOperation]:
    return [op for op in sess.operations if op.status == "active"]


def _active_seqs(sess: AnalysisSession) -> list[int]:
    return [op.sequence_number for op in _active(sess)]


def _chain(sess: AnalysisSession, upto: int) -> list[dict[str, Any]]:
    return [
        {"seq": op.sequence_number, "type": op.operation_type, "parameters": op.parameters_json}
        for op in _active(sess)
        if op.sequence_number <= upto
    ]


def _settings(sess: AnalysisSession) -> dict[str, Any]:
    return {"sensitive": list(sess.sensitive_columns_json or []), "date_rules": dict(sess.date_rules_json or {})}


class _Lock:
    def __init__(self, session_id: str):
        self.lock = _locks[session_id]

    def __enter__(self):
        if not self.lock.acquire(blocking=False):
            raise AppError(409, "BUSY", "Another change to this dataset is still being applied. Please wait.")
        return self

    def __exit__(self, *exc):
        self.lock.release()


def operation_out(op: CleaningOperation) -> OperationOut:
    spec = REGISTRY.get(op.operation_type)
    meta = snapshots.read_meta(op.session.dataset_id, op.session_id, op.sequence_number) or {}
    return OperationOut(
        id=op.id,
        sequence_number=op.sequence_number,
        operation_type=op.operation_type,
        title=spec.title if spec else op.operation_type,
        parameters=op.parameters_json,
        affected_rows=op.affected_rows,
        status=op.status,
        created_at=op.created_at,
        undone_at=op.undone_at,
        summary=(meta.get("operation") or {}).get("summary"),
    )


@router.get("/cleaning/operations")
def list_operations() -> list[dict[str, Any]]:
    return catalogue()


@router.post("/sessions/{session_id}/cleaning/preview", dependencies=[Depends(rate_limit("clean"))])
async def preview(
    session_id: str, body: CleaningRequest, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    engine.validate(body.operation_type, body.parameters)  # fast feedback before starting a worker
    dataset_id, version, ctx = sess.dataset_id, current_version(sess), _ctx(sess)
    await _ensure_current(sess)
    db.rollback()
    return await run_in_threadpool(
        run_limited, engine.preview_task, dataset_id, session_id, version, body.operation_type, body.parameters, ctx
    )


async def _ensure_current(sess: AnalysisSession) -> None:
    """Rebuild the current snapshot if it is not on disk (older versions are pruned)."""
    version = current_version(sess)
    if version and not snapshots.exists(sess.dataset_id, sess.id, version):
        await run_in_threadpool(
            run_limited, materialize_task, sess.dataset_id, sess.id, version, _chain(sess, version), _ctx(sess)
        )


@router.post("/sessions/{session_id}/cleaning/apply", dependencies=[Depends(rate_limit("clean"))])
async def apply(
    session_id: str, body: CleaningRequest, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    spec, params = engine.validate(body.operation_type, body.parameters)
    if spec.destructive(params) and not body.confirm:
        raise AppError(409, "CONFIRMATION_REQUIRED", "This change removes or overwrites data. Please confirm it.")
    with _Lock(session_id):
        await _ensure_current(sess)
        dataset_id, version, ctx = sess.dataset_id, current_version(sess), _ctx(sess)
        new_seq = max((op.sequence_number for op in sess.operations), default=0) + 1
        db.rollback()  # never hold a transaction during slow work
        result = await run_in_threadpool(
            run_limited,
            engine.apply_task,
            dataset_id,
            session_id,
            version,
            new_seq,
            body.operation_type,
            body.parameters,
            ctx,
        )
        if result["affected_rows"] == 0:
            raise AppError(422, "NOTHING_TO_CHANGE", f"Nothing to change: {result['summary']}")
        try:
            sess = owned_session(db, ws, session_id)
            snapshots.update_meta(dataset_id, session_id, new_seq, settings_before=_settings(sess))
            op = CleaningOperation(
                session_id=session_id,
                sequence_number=new_seq,
                operation_type=spec.id,
                parameters_json=result["parameters"],
                affected_rows=result["affected_rows"],
            )
            db.add(op)
            db.flush()
            db.add(
                AuditEvent(
                    session_id=session_id,
                    event_type="apply",
                    details_json={
                        "operation_id": op.id,
                        "sequence_number": new_seq,
                        "operation_type": spec.id,
                        "title": spec.title,
                        "affected_rows": result["affected_rows"],
                        "summary": result["summary"],
                    },
                )
            )
            _carry_session_settings(sess, result)
            db.commit()
        except BaseException:
            db.rollback()
            remove(snapshots.snapshot_path(dataset_id, session_id, new_seq))
            remove(snapshots.meta_path(dataset_id, session_id, new_seq))
            raise
        db.refresh(sess)
        await run_in_threadpool(prune, dataset_id, session_id, _active_seqs(sess))
        return {
            "operation": operation_out(op).model_dump(mode="json"),
            "result": result,
            "session": session_out(sess).model_dump(mode="json"),
        }


def _carry_session_settings(sess: AnalysisSession, result: dict[str, Any]) -> None:
    """Keep sensitive columns and confirmed date readings attached to the right (possibly renamed) columns."""
    renamed: dict[str, str] = result.get("renamed") or {}
    removed = set(result.get("removed_columns") or [])
    sensitive = [renamed.get(c, c) for c in (sess.sensitive_columns_json or []) if c not in removed]
    if sensitive != (sess.sensitive_columns_json or []):
        sess.sensitive_columns_json = sensitive
    rules = dict(sess.date_rules_json or {})
    cols = {renamed.get(c, c): v for c, v in (rules.get("columns") or {}).items() if c not in removed}
    if result.get("date_rule"):
        column, interpretation = result["date_rule"]
        cols[column] = interpretation
    if cols != (rules.get("columns") or {}):
        sess.date_rules_json = {**rules, "columns": cols}


def _restore_settings(sess: AnalysisSession, undone: list[CleaningOperation]) -> None:
    """Reverse the column-name effects of undone operations (newest first) on the session's settings.

    Date readings only come from operations, so they return to exactly what they were before the oldest
    undone operation. Sensitive marks can also be changed by the user at any time, so they are adjusted:
    renames are reversed, and columns that come back after an undone removal regain their mark.
    """
    sensitive = list(sess.sensitive_columns_json or [])
    oldest_before: dict[str, Any] | None = None
    for op in undone:  # newest first
        meta = snapshots.read_meta(sess.dataset_id, sess.id, op.sequence_number) or {}
        before = meta.get("settings_before") or {}
        oldest_before = before
        if op.operation_type == "rename_columns":
            inverse = {new: old for old, new in (op.parameters_json.get("mapping") or {}).items()}
            sensitive = [inverse.get(c, c) for c in sensitive]
        if op.operation_type == "remove_columns":
            for c in op.parameters_json.get("columns") or []:
                if c in (before.get("sensitive") or []) and c not in sensitive:
                    sensitive.append(c)
    sess.sensitive_columns_json = sensitive
    if oldest_before is not None:
        sess.date_rules_json = oldest_before.get("date_rules") or {}


async def _undo(db: Session, ws: Workspace, session_id: str, count: int | None, event: str) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    active = _active(sess)
    if not active:
        raise AppError(
            409,
            "NOTHING_TO_UNDO" if event == "undo" else "ALREADY_ORIGINAL",
            "There are no changes to undo." if event == "undo" else "The data is already the original.",
        )
    targets = list(reversed(active))[: count or len(active)]
    with _Lock(session_id):
        now = utcnow()
        for op in targets:
            op.status, op.undone_at = "undone", now
        _restore_settings(sess, targets)
        db.add(
            AuditEvent(
                session_id=session_id,
                event_type=event,
                details_json={
                    "operations": [
                        {
                            "operation_id": op.id,
                            "sequence_number": op.sequence_number,
                            "operation_type": op.operation_type,
                            "title": REGISTRY[op.operation_type].title
                            if op.operation_type in REGISTRY
                            else op.operation_type,
                        }
                        for op in targets
                    ],
                    "version_after": current_version(sess),
                },
            )
        )
        sess.updated_at = now
        db.commit()
        db.refresh(sess)
        await _ensure_current(sess)
        await run_in_threadpool(prune, sess.dataset_id, session_id, _active_seqs(sess))
    return {"undone": [op.sequence_number for op in targets], "session": session_out(sess).model_dump(mode="json")}


@router.post("/sessions/{session_id}/cleaning/undo", dependencies=[Depends(rate_limit("clean"))])
async def undo(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return await _undo(db, ws, session_id, 1, "undo")


@router.post("/sessions/{session_id}/cleaning/reset", dependencies=[Depends(rate_limit("clean"))])
async def reset(
    session_id: str, body: ResetRequest, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    if not body.confirm:
        raise AppError(409, "CONFIRMATION_REQUIRED", "Resetting undoes every change. Please confirm it.")
    return await _undo(db, ws, session_id, None, "reset")


@router.get("/sessions/{session_id}/cleaning/category-suggestions", dependencies=[Depends(rate_limit("query"))])
async def suggestions(
    session_id: str,
    column: str = Query(..., max_length=200),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    await _ensure_current(sess)
    df = await run_in_threadpool(snapshots.load, sess.dataset_id, sess.id, current_version(sess))
    if column not in df.columns:
        raise AppError(422, "UNKNOWN_COLUMN", "Unknown column.")
    groups = await run_in_threadpool(category_suggestions, df[column])
    return {"column": column, "groups": groups}


@router.get("/sessions/{session_id}/history", response_model=list[OperationOut])
def history(session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    sess = owned_session(db, ws, session_id)
    return [operation_out(op) for op in sess.operations]


@router.get("/sessions/{session_id}/timeline")
def timeline(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """The audit trail: every apply, undo, reset and privacy change, oldest first."""
    sess = owned_session(db, ws, session_id)
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.session_id == sess.id).order_by(AuditEvent.created_at, AuditEvent.id)
    ).all()
    return {
        "operations": [operation_out(op).model_dump(mode="json") for op in sess.operations],
        "events": [
            {"id": e.id, "type": e.event_type, "details": e.details_json, "created_at": e.created_at.isoformat()}
            for e in events
        ],
        "current_version": current_version(sess),
    }


# ---------- before / after ----------


def _column_origins(sess: AnalysisSession, original_columns: list[str]) -> dict[str, str]:
    ops = [{"type": op.operation_type, "parameters": op.parameters_json} for op in _active(sess)]
    return column_origins(ops, original_columns)


@router.get("/sessions/{session_id}/compare", dependencies=[Depends(rate_limit("query"))])
async def compare(
    session_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    changed_only: bool = True,
    columns: list[str] = Query(default_factory=list, max_length=20),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Original vs current, aligned by original row. Rows removed by cleaning are listed as removed."""
    sess = owned_session(db, ws, session_id)
    await _ensure_current(sess)
    original = await run_in_threadpool(snapshots.load, sess.dataset_id, sess.id, 0)
    current = await run_in_threadpool(snapshots.load, sess.dataset_id, sess.id, current_version(sess))
    origins = _column_origins(sess, [str(c) for c in original.columns])
    cols = columns or [str(c) for c in current.columns[:6]]
    unknown = [c for c in cols if c not in current.columns]
    if unknown:
        raise AppError(422, "UNKNOWN_COLUMN", f"Unknown column(s): {', '.join(unknown[:5])}")

    def build() -> dict[str, Any]:
        present = original.index.isin(current.index)
        changed = ~present
        aligned = current.reindex(original.index[present])
        for c in cols:
            src = origins.get(c)
            if src is None:
                continue  # a new column (e.g. a flag) is not a change to existing data
            mask = np.zeros(len(original), dtype=bool)
            before = original.loc[present, src]
            after = aligned[c]
            mask[np.flatnonzero(present)] = [
                not _same(a, b) for a, b in zip(before.to_numpy(), after.to_numpy(), strict=True)
            ]
            changed |= mask
        labels = original.index[changed] if changed_only else original.index
        page = labels[offset : offset + limit]
        rows = []
        for label in page:
            removed = label not in current.index
            cells = []
            for c in cols:
                src = origins.get(c)
                b = original.at[label, src] if src is not None else None
                a = None if removed else current.at[label, c]
                cells.append(
                    {
                        "before": None if src is None or b is None else display_value(b),
                        "after": None if removed or a is None else display_value(a),
                        "changed": bool(removed or (src is not None and not _same(b, a))),
                        "new_column": src is None,
                    }
                )
            rows.append({"row": int(label) + sess.header_row + 2, "removed": removed, "cells": cells})
        return {
            "columns": [{"name": c, "original": origins.get(c)} for c in cols],
            "total": int(len(labels)),
            "changed_rows": int(changed.sum()),
            "removed_rows": int((~present).sum()),
            "offset": offset,
            "rows": rows,
            "version": current_version(sess),
        }

    return await run_in_threadpool(build)
