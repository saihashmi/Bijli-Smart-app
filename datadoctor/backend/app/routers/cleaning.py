"""Cleaning Studio API: operation catalogue, preview (no changes), apply (new snapshot + audit), history."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import AppError
from ..middleware.ratelimit import rate_limit
from ..middleware.workspace import current_workspace, owned_session
from ..models import CleaningOperation, Workspace
from ..schemas.datasets import CleaningRequest, OperationOut
from ..services.cleaning import engine
from ..services.cleaning.ops import category_suggestions
from ..services.cleaning.registry import REGISTRY, catalogue
from ..services.storage import snapshots
from ..services.storage.paths import remove
from ..worker import run_limited
from .sessions import current_version, session_out

router = APIRouter(prefix="/api", tags=["cleaning"])

# One cleaning change at a time per session (single API process; see CLAUDE.md).
_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


def _ctx(sess) -> dict[str, Any]:
    return {"header_row": sess.header_row}


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
    db.rollback()
    return await run_in_threadpool(
        run_limited, engine.preview_task, dataset_id, session_id, version, body.operation_type, body.parameters, ctx
    )


@router.post("/sessions/{session_id}/cleaning/apply", dependencies=[Depends(rate_limit("clean"))])
async def apply(
    session_id: str, body: CleaningRequest, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    spec, params = engine.validate(body.operation_type, body.parameters)
    if spec.destructive(params) and not body.confirm:
        raise AppError(409, "CONFIRMATION_REQUIRED", "This change removes or overwrites data. Please confirm it.")
    lock = _locks[session_id]
    if not lock.acquire(blocking=False):
        raise AppError(409, "BUSY", "Another change to this dataset is still being applied. Please wait.")
    try:
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
            op = CleaningOperation(
                session_id=session_id,
                sequence_number=new_seq,
                operation_type=spec.id,
                parameters_json=result["parameters"],
                affected_rows=result["affected_rows"],
            )
            db.add(op)
            _carry_session_settings(sess, result)
            db.commit()
        except BaseException:
            db.rollback()
            remove(snapshots.snapshot_path(dataset_id, session_id, new_seq))
            remove(snapshots.meta_path(dataset_id, session_id, new_seq))
            raise
        db.refresh(sess)
        return {
            "operation": operation_out(op).model_dump(mode="json"),
            "result": result,
            "session": session_out(sess).model_dump(mode="json"),
        }
    finally:
        lock.release()


def _carry_session_settings(sess, result: dict[str, Any]) -> None:
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


@router.get("/sessions/{session_id}/cleaning/category-suggestions", dependencies=[Depends(rate_limit("query"))])
async def suggestions(
    session_id: str,
    column: str = Query(..., max_length=200),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    df = await run_in_threadpool(snapshots.load, sess.dataset_id, sess.id, current_version(sess))
    if column not in df.columns:
        raise AppError(422, "UNKNOWN_COLUMN", "Unknown column.")
    groups = await run_in_threadpool(category_suggestions, df[column])
    return {"column": column, "groups": groups}


@router.get("/sessions/{session_id}/history", response_model=list[OperationOut])
def history(session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    sess = owned_session(db, ws, session_id)
    return [operation_out(op) for op in sess.operations]
