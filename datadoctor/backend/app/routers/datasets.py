"""Upload, worksheet discovery, peeks, and analysis-session creation (Milestone 4)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..errors import AppError
from ..middleware.ratelimit import rate_limit
from ..middleware.workspace import current_workspace, owned_dataset, owned_session
from ..models import AnalysisSession, Dataset, Worksheet, Workspace, utcnow
from ..schemas.datasets import CsvInfo, DatasetOut, PeekOut, SessionBrief, SessionCreate, SessionOut, SheetOut
from ..services.ingest import csvfile, discovery, files
from ..services.ingest.errors import IngestError
from ..services.storage.paths import remove, remove_dataset_files, safe_path

router = APIRouter(prefix="/api", tags=["datasets"])

CHUNK = 1024 * 1024
STORED_EXT = {"xlsx": "xlsx", "xls": "xls", "csv": "csv"}


def _original_path(ds: Dataset) -> Path:
    return safe_path("originals", ds.storage_reference)


def _sheet_out(ws: Worksheet) -> SheetOut:
    problem = None
    if ws.row_count is None or ws.column_count is None:
        problem = "This sheet could not be read."
    elif ws.row_count == 0 or ws.column_count == 0:
        problem = "This sheet is empty."
    else:
        problem = discovery.limit_problem(ws.row_count, ws.column_count)
    return SheetOut(
        index=ws.sheet_index,
        name=ws.sheet_name,
        visibility=ws.visibility,
        rows=ws.row_count or 0,
        columns=ws.column_count or 0,
        formula_cells_without_cache=ws.formula_cells_without_cache,
        selectable=problem is None,
        problem=problem,
    )


def _session_brief(sess: AnalysisSession, sheets: dict[str, Worksheet]) -> SessionBrief:
    ws = sheets.get(sess.worksheet_id or "")
    return SessionBrief(
        id=sess.id,
        sheet_index=ws.sheet_index if ws else None,
        sheet_name=ws.sheet_name if ws else None,
        header_row=sess.header_row,
        status=sess.status,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
    )


def _dataset_out(ds: Dataset, warnings: list[str] | None = None, csv: csvfile.CsvFormat | None = None) -> DatasetOut:
    sheets = sorted(ds.worksheets, key=lambda w: w.sheet_index)
    by_id = {w.id: w for w in sheets}
    if ds.file_type == "csv" and csv is None:
        csv = csvfile.detect_format(_original_path(ds))
    return DatasetOut(
        id=ds.id,
        original_filename=ds.original_filename,
        file_type=ds.file_type,
        file_size=ds.file_size,
        uploaded_at=ds.uploaded_at,
        expires_at=ds.expires_at,
        status=ds.status,
        sheets=[_sheet_out(w) for w in sheets],
        csv=CsvInfo(
            encoding=csv.encoding,
            delimiter=csv.delimiter,
            delimiter_label=csv.delimiter_label,
            replaced_characters=csv.replaced_characters,
        )
        if csv
        else None,
        warnings=warnings or [],
        sessions=[_session_brief(s, by_id) for s in ds.sessions if s.status == "active"],
    )


def _session_out(sess: AnalysisSession) -> SessionOut:
    ds = sess.dataset
    ws = next((w for w in ds.worksheets if w.id == sess.worksheet_id), None)
    return SessionOut(
        id=sess.id,
        dataset_id=ds.id,
        original_filename=ds.original_filename,
        file_type=ds.file_type,
        sheet_index=ws.sheet_index if ws else None,
        sheet_name=ws.sheet_name if ws else None,
        header_row=sess.header_row,
        rows=ws.row_count if ws else None,
        columns=ws.column_count if ws else None,
        status=sess.status,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
        expires_at=ds.expires_at,
    )


@router.post("/uploads", response_model=DatasetOut, status_code=201, dependencies=[Depends(rate_limit("upload"))])
async def upload(
    file: UploadFile = File(...), ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
):
    display_name = files.sanitize_filename(file.filename)
    declared_kind = files.extension_kind(display_name)
    dataset_id = str(uuid.uuid4())
    tmp = safe_path("originals", f"{dataset_id}.part")
    limit = settings.max_upload_mb * 1024 * 1024
    digest, size = hashlib.sha256(), 0
    final: Path | None = None
    try:
        with tmp.open("wb") as out:
            while chunk := await file.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise IngestError(
                        "FILE_TOO_LARGE", f"The file is larger than the {settings.max_upload_mb} MB limit.", 413
                    )
                digest.update(chunk)
                out.write(chunk)
        check = await run_in_threadpool(files.check_content, tmp, declared_kind)
        final = safe_path("originals", f"{dataset_id}.{STORED_EXT[check.kind]}")
        tmp.rename(final)
        found = await run_in_threadpool(discovery.discover, final, check.kind)
    except BaseException:
        remove(tmp)
        if final is not None:
            remove(final)
        raise

    ds = Dataset(
        id=dataset_id,
        workspace_id=ws.id,
        original_filename=display_name,
        file_type=check.kind,
        file_size=size,
        sha256=digest.hexdigest(),
        storage_reference=final.name,
        expires_at=utcnow() + timedelta(days=settings.retention_days),
        status="uploaded",
    )
    for sh in found.sheets:
        if sh.kind != "worksheet":
            continue  # chart sheets hold no table data; reported as a warning below
        ds.worksheets.append(
            Worksheet(
                sheet_name=sh.name[:255],
                sheet_index=sh.index,
                visibility=sh.visibility,
                row_count=sh.rows,
                column_count=sh.columns,
                formula_cells_without_cache=sh.formula_cells_without_cache,
            )
        )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    warnings = check.warnings + found.warnings
    for sh in found.sheets:
        if sh.kind != "worksheet":
            warnings.append(f"'{sh.name}' is a chart sheet and has no table data.")
    return _dataset_out(ds, warnings=warnings, csv=found.csv)


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Dataset)
        .where(Dataset.workspace_id == ws.id, Dataset.status != "deleted")
        .order_by(Dataset.uploaded_at.desc())
    ).all()
    return [_dataset_out(d) for d in rows]


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    return _dataset_out(owned_dataset(db, ws, dataset_id))


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    ds = owned_dataset(db, ws, dataset_id)
    remove_dataset_files(ds.id, ds.storage_reference)
    db.delete(ds)
    db.commit()


@router.get(
    "/datasets/{dataset_id}/sheets/{sheet_index}/peek",
    response_model=PeekOut,
    dependencies=[Depends(rate_limit("query"))],
)
async def peek_sheet(
    dataset_id: str,
    sheet_index: int,
    rows: int = Query(15, ge=1, le=60),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
):
    ds = owned_dataset(db, ws, dataset_id)
    sheet = next((w for w in ds.worksheets if w.sheet_index == sheet_index), None)
    if sheet is None:
        raise AppError(404, "SHEET_NOT_FOUND", "That worksheet does not exist.")
    data = await run_in_threadpool(discovery.peek, _original_path(ds), ds.file_type, sheet_index, rows, 50)
    return PeekOut(
        sheet_index=sheet_index,
        rows=data,
        total_rows=sheet.row_count or 0,
        total_columns=sheet.column_count or 0,
        truncated_columns=(sheet.column_count or 0) > 50,
    )


@router.post("/datasets/{dataset_id}/sessions", response_model=SessionOut, status_code=201)
def create_session(
    dataset_id: str, body: SessionCreate, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
):
    ds = owned_dataset(db, ws, dataset_id)
    sheet = next((w for w in ds.worksheets if w.sheet_index == body.sheet_index), None)
    if sheet is None:
        raise AppError(404, "SHEET_NOT_FOUND", "That worksheet does not exist.")
    info = _sheet_out(sheet)
    if not info.selectable:
        raise AppError(422, "SHEET_NOT_USABLE", info.problem or "This sheet cannot be analysed.")
    if body.header_row >= (sheet.row_count or 0):
        raise AppError(422, "INVALID_HEADER_ROW", "The header row is beyond the last row of the sheet.")
    sess = AnalysisSession(dataset_id=ds.id, worksheet_id=sheet.id, header_row=body.header_row)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return _session_out(sess)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(AnalysisSession)
        .join(Dataset)
        .where(Dataset.workspace_id == ws.id, AnalysisSession.status == "active", Dataset.status != "deleted")
        .order_by(AnalysisSession.updated_at.desc())
    ).all()
    return [_session_out(s) for s in rows]


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    return _session_out(owned_session(db, ws, session_id))


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    sess = owned_session(db, ws, session_id)
    snap = settings.storage_dir / "snapshots" / sess.dataset_id / sess.id
    if snap.exists():
        remove(snap)
    db.delete(sess)
    db.commit()
