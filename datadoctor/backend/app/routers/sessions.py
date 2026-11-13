"""Analysis sessions: creation (parses the sheet into snapshot v0), summary, paged rows and column profile."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import AppError
from ..middleware.ratelimit import rate_limit
from ..middleware.workspace import current_workspace, owned_dataset, owned_session
from ..models import AnalysisSession, AuditEvent, DataProfile, Dataset, Workspace, new_id
from ..schemas.datasets import RowsOut, SensitiveColumnsIn, SessionCreate, SessionOut
from ..services.cleaning.lineage import column_origins
from ..services.ingest.parse import parse_to_snapshot
from ..services.ingest.workbook import display_value
from ..services.profiling import drilldown
from ..services.profiling.health import finalize
from ..services.profiling.tasks import PROFILE_SCHEMA, profile_snapshot
from ..services.storage import snapshots
from ..services.storage.paths import remove
from ..worker import run_limited
from .datasets import original_path, sheet_out

router = APIRouter(prefix="/api", tags=["sessions"])
_profile_locks: defaultdict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)

MAX_PAGE = 500


def current_version(sess: AnalysisSession) -> int:
    """Snapshot version holding the current data: the sequence number of the last active operation (0 = original)."""
    active = [op.sequence_number for op in sess.operations if op.status == "active"]
    return max(active) if active else 0


def version_hash(sess: AnalysisSession) -> str:
    active = [op.id for op in sess.operations if op.status == "active"]
    return hashlib.sha256(json.dumps([PROFILE_SCHEMA, active]).encode()).hexdigest()


def session_out(sess: AnalysisSession) -> SessionOut:
    ds = sess.dataset
    ws = next((w for w in ds.worksheets if w.id == sess.worksheet_id), None)
    version = current_version(sess)
    meta = snapshots.read_meta(ds.id, sess.id, version) or snapshots.read_meta(ds.id, sess.id, 0) or {}
    return SessionOut(
        id=sess.id,
        dataset_id=ds.id,
        original_filename=ds.original_filename,
        file_type=ds.file_type,
        file_size=ds.file_size,
        sheet_index=ws.sheet_index if ws else None,
        sheet_name=ws.sheet_name if ws else None,
        header_row=sess.header_row,
        rows=meta.get("rows"),
        columns=len(meta.get("columns", [])) if meta else None,
        column_names=meta.get("columns", []),
        header_changes=meta.get("header_changes", []),
        warnings=meta.get("warnings", []),
        version=version,
        status=sess.status,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
        expires_at=ds.expires_at,
    )


@router.post(
    "/datasets/{dataset_id}/sessions",
    response_model=SessionOut,
    status_code=201,
    dependencies=[Depends(rate_limit("profile"))],
)
async def create_session(
    dataset_id: str, body: SessionCreate, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
):
    ds = owned_dataset(db, ws, dataset_id)
    sheet = next((w for w in ds.worksheets if w.sheet_index == body.sheet_index), None)
    if sheet is None:
        raise AppError(404, "SHEET_NOT_FOUND", "That worksheet does not exist.")
    info = sheet_out(sheet)
    if not info.selectable:
        raise AppError(422, "SHEET_NOT_USABLE", info.problem or "This sheet cannot be analysed.")
    if body.header_row >= (sheet.row_count or 0):
        raise AppError(422, "INVALID_HEADER_ROW", "The header row is beyond the last row of the sheet.")

    # Read the sheet BEFORE writing to the database: holding a write transaction open during slow work
    # locks SQLite for every other request (found by concurrent browser tests in Milestone 5).
    dataset_id, file_type, sheet_id, sheet_index = ds.id, ds.file_type, sheet.id, sheet.sheet_index
    source = str(original_path(ds))
    session_id = new_id()
    db.rollback()  # end the read transaction before the long-running step
    try:
        await run_in_threadpool(
            run_limited, parse_to_snapshot, source, file_type, sheet_index, body.header_row, dataset_id, session_id
        )
    except BaseException:
        remove(snapshots.snapshot_dir(dataset_id, session_id))
        raise
    sess = AnalysisSession(id=session_id, dataset_id=dataset_id, worksheet_id=sheet_id, header_row=body.header_row)
    db.add(sess)
    ds = db.get(Dataset, dataset_id)
    if ds is None:  # deleted while we were parsing
        remove(snapshots.snapshot_dir(dataset_id, session_id))
        raise AppError(404, "NOT_FOUND", "Dataset not found.")
    ds.status = "parsed"
    db.commit()
    db.refresh(sess)
    return session_out(sess)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(AnalysisSession)
        .join(Dataset)
        .where(Dataset.workspace_id == ws.id, AnalysisSession.status == "active", Dataset.status != "deleted")
        .order_by(AnalysisSession.updated_at.desc())
    ).all()
    return [session_out(s) for s in rows]


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    return session_out(owned_session(db, ws, session_id))


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    sess = owned_session(db, ws, session_id)
    folder = snapshots.snapshot_dir(sess.dataset_id, sess.id)
    snapshots.forget(str(folder))
    remove(folder)
    db.delete(sess)
    db.commit()


def _require_snapshot(sess: AnalysisSession, version: int) -> None:
    if not snapshots.exists(sess.dataset_id, sess.id, version):
        raise AppError(410, "DATA_UNAVAILABLE", "The data for this session is no longer available.")


@router.get("/sessions/{session_id}/rows", response_model=RowsOut, dependencies=[Depends(rate_limit("query"))])
async def get_rows(
    session_id: str,
    view: str = Query("current", pattern="^(current|original)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=MAX_PAGE),
    flags: bool = False,
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
):
    sess = owned_session(db, ws, session_id)
    version = 0 if view == "original" else current_version(sess)
    _require_snapshot(sess, version)
    df = await run_in_threadpool(snapshots.load, sess.dataset_id, sess.id, version)
    page = df.iloc[offset : offset + limit]
    rows = [[None if v is None else display_value(v) for v in row] for row in page.itertuples(index=False)]
    # Spreadsheet row numbers of these rows (the index keeps each row's original position through cleaning).
    row_numbers = [int(i) + sess.header_row + 2 for i in page.index]
    cell_flags: list[list[str]] | None = None
    row_flags: list[str] | None = None
    if flags:
        vhash = version_hash(sess)
        cached = db.scalars(
            select(DataProfile).where(DataProfile.session_id == sess.id, DataProfile.version_hash == vhash)
        ).first()
        families = {c["name"]: c.get("family") for c in (cached.profile_json["column_profiles"] if cached else [])}
        path = snapshots.snapshot_path(sess.dataset_id, sess.id, version)
        dup_all = await run_in_threadpool(drilldown.duplicate_mask, df, (str(path), path.stat().st_mtime))
        original = origins = None
        if version != 0:
            original = await run_in_threadpool(snapshots.load, sess.dataset_id, sess.id, 0)
            ops = [
                {"type": o.operation_type, "parameters": o.parameters_json}
                for o in sess.operations
                if o.status == "active"
            ]
            origins = column_origins(ops, [str(c) for c in original.columns])
        cell_flags, row_flags = await run_in_threadpool(
            drilldown.cell_flags, page, families, dup_all[offset : offset + limit], original, origins or {}
        )
    return RowsOut(
        view=view,
        version=version,
        offset=offset,
        total=len(df),
        columns=[str(c) for c in df.columns],
        rows=rows,
        row_numbers=row_numbers,
        cell_flags=cell_flags,
        row_flags=row_flags,
    )


@router.get("/sessions/{session_id}/issues/{issue_id}/rows", dependencies=[Depends(rate_limit("query"))])
async def issue_rows(
    session_id: str,
    issue_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """The rows an issue affects (drill-down from the Data Health Center). `issue_id` is "<code>:<column or *>"."""
    sess = owned_session(db, ws, session_id)
    code, _, col = issue_id.partition(":")
    column = None if col in ("", "*") else col
    if code in drilldown.NO_ROW_VIEW:
        raise AppError(422, "NO_ROW_VIEW", "This issue is about the sheet structure, not particular rows.")
    version = current_version(sess)
    _require_snapshot(sess, version)
    df = await run_in_threadpool(snapshots.load, sess.dataset_id, sess.id, version)
    context = {"file_type": sess.dataset.file_type}
    try:
        mask = await run_in_threadpool(drilldown.issue_mask, df, code, column, context)
    except KeyError:
        raise AppError(404, "ISSUE_NOT_FOUND", "That issue does not exist for this dataset.") from None
    hits = df[mask]
    page = hits.iloc[offset : offset + limit]
    # Show the issue's column first, then a few neighbours for context.
    cols = ([column] if column else []) + [str(c) for c in df.columns if str(c) != column][: 6 if column else 7]
    return {
        "issue_id": issue_id,
        "total": int(mask.sum()),
        "offset": offset,
        "columns": cols,
        "highlight": column,
        "rows": [
            {
                "row": int(i) + sess.header_row + 2,
                "values": [None if page.at[i, c] is None else display_value(page.at[i, c]) for c in cols],
            }
            for i in page.index
        ],
    }


@router.get("/sessions/{session_id}/profile", dependencies=[Depends(rate_limit("profile"))])
async def get_profile(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    version = current_version(sess)
    vhash = version_hash(sess)

    def lookup():
        return db.scalars(
            select(DataProfile).where(DataProfile.session_id == session_id, DataProfile.version_hash == vhash)
        ).first()

    cached = lookup()
    if cached is None:
        # Identical concurrent requests wait for the first computation instead of repeating it.
        async with _profile_locks[(session_id, vhash)]:
            db.rollback()
            cached = lookup()
            if cached is None:
                cached = await _compute_profile(db, ws, session_id, version, vhash)
        _profile_locks.pop((session_id, vhash), None)
        sess = owned_session(db, ws, session_id)
    final = finalize(cached.profile_json, sess.sensitive_columns_json or [], sess.date_rules_json or {})
    return {"session_id": session_id, "version": version, "calculated_at": cached.calculated_at.isoformat(), **final}


async def _compute_profile(db: Session, ws: Workspace, session_id: str, version: int, vhash: str) -> DataProfile:
    sess = owned_session(db, ws, session_id)
    _require_snapshot(sess, version)
    dataset_id, sid = sess.dataset_id, sess.id
    meta = snapshots.read_meta(dataset_id, sid, 0) or {}
    ws_row = next((w for w in sess.dataset.worksheets if w.id == sess.worksheet_id), None)
    context = {
        "header_row": sess.header_row,
        "header_changes": meta.get("header_changes", []),
        "file_type": sess.dataset.file_type,
        "formula_cells_without_cache": ws_row.formula_cells_without_cache if ws_row else 0,
    }
    db.rollback()  # no transaction held during the slow step
    try:
        result = await run_in_threadpool(run_limited, profile_snapshot, dataset_id, sid, version, context)
    except AppError:
        db.expire_all()
        fresh = db.get(AnalysisSession, sid)
        if fresh is not None and current_version(fresh) != version:
            # An undo or reset replaced this version while it was being analysed; its snapshot may be gone.
            raise AppError(409, "VERSION_CHANGED", "The data changed while it was being analysed.") from None
        raise
    cached = DataProfile(session_id=sid, version_hash=vhash, profile_json=result)
    db.add(cached)
    db.commit()
    return cached


@router.put("/sessions/{session_id}/sensitive-columns")
def set_sensitive_columns(
    session_id: str, body: SensitiveColumnsIn, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, list[str]]:
    sess = owned_session(db, ws, session_id)
    meta = snapshots.read_meta(sess.dataset_id, sess.id, 0) or {}
    known = set(meta.get("columns", []))
    unknown = [c for c in body.columns if c not in known]
    if unknown:
        raise AppError(422, "UNKNOWN_COLUMN", f"Unknown column(s): {', '.join(unknown[:5])}")
    ordered = [c for c in meta.get("columns", []) if c in set(body.columns)]
    before = sess.sensitive_columns_json or []
    if ordered != before:
        sess.sensitive_columns_json = ordered
        db.add(
            AuditEvent(
                session_id=sess.id,
                event_type="sensitive_columns",
                details_json={
                    "added": [c for c in ordered if c not in before],
                    "removed": [c for c in before if c not in ordered],
                },
            )
        )
        db.commit()
    return {"sensitive_columns": ordered}
