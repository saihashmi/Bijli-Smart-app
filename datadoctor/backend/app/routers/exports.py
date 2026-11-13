"""Exports API (SPEC FR-6): Excel workbook and PDF report, downloadable only by the owning workspace."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import AppError
from ..middleware.ratelimit import rate_limit
from ..middleware.workspace import current_workspace, owned_session
from ..models import (
    AIInteraction,
    AnalysisSession,
    AuditEvent,
    DashboardConfiguration,
    ExportJob,
    Worksheet,
    Workspace,
    new_id,
    utcnow,
)
from ..schemas.settings import Preferences
from ..security import sign, unsign
from ..services.analytics import query as aq
from ..services.cleaning.registry import SPECS
from ..services.reports.tasks import export_task
from ..services.storage.paths import remove, safe_path
from ..worker import run_limited
from .analytics import DashboardIn, _typed
from .sessions import current_version, get_profile

router = APIRouter(prefix="/api", tags=["exports"])

LINK_TTL_S = 600
FILE_TTL = timedelta(hours=24)
MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
TITLES = {s.id: s.title for s in SPECS}


class ExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["xlsx", "pdf"]
    include_dashboard: bool = True
    include_answers: bool = True


def _stamp(zone: str) -> str:
    now = datetime.now(ZoneInfo(zone))
    return f"{now:%d %b %Y %H:%M} {now.tzname()} ({zone})"


def _link(job: ExportJob) -> str | None:
    if job.status != "done" or (job.expires_at and job.expires_at < utcnow()):
        return None
    token = sign(f"{job.id}:{int(time.time()) + LINK_TTL_S}", "export")
    return f"/api/exports/{job.id}/download?token={token}"


def _out(job: ExportJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "type": job.export_type,
        "status": job.status,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "expires_at": job.expires_at,
        "error": job.error,
        "details": job.options_json.get("result"),
        "file_name": job.options_json.get("file_name"),
        "download_url": _link(job),
        "link_valid_seconds": LINK_TTL_S,
    }


def _file_name(original: str, kind: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", original)
    stem = re.sub(r"[^A-Za-z0-9 _.-]+", "", stem).strip(" .")[:80] or "data"
    return f"{stem} - {'cleaned' if kind == 'xlsx' else 'report'}.{kind}"


def _describe_filter(f: Any) -> str:
    if f.op == "range":
        return f"{f.column} between {f.min if f.min is not None else 'any'} and {f.max if f.max is not None else 'any'}"
    if f.op == "date_range":
        return f"{f.column} from {f.start or 'the start'} to {f.end or 'the end'}"
    values = ", ".join(f.values[:5]) + (" and more" if len(f.values) > 5 else "")
    return f"{f.column} {'is' if f.op == 'in' else 'is not'} {values}"


async def _context(sess: AnalysisSession, ws: Workspace, db: Session, body: ExportIn) -> dict[str, Any]:
    prefs = Preferences(**(ws.settings_json or {}))
    profile = await get_profile(sess.id, ws, db)
    ops = sorted(sess.operations, key=lambda o: o.sequence_number)
    zone = ZoneInfo(prefs.display_timezone)
    sheet = db.get(Worksheet, sess.worksheet_id) if sess.worksheet_id else None
    ctx: dict[str, Any] = {
        "generated_at": _stamp(prefs.display_timezone),
        "filename": sess.dataset.original_filename,
        "sheet_name": sheet.sheet_name if sheet else "",
        "version": current_version(sess),
        "active_steps": sum(1 for o in ops if o.status == "active"),
        "profile": profile,
        "operations": [
            {
                "sequence": o.sequence_number,
                "title": TITLES.get(o.operation_type, o.operation_type),
                "parameters": json.dumps(o.parameters_json, ensure_ascii=False, sort_keys=True),
                "affected_rows": o.affected_rows,
                "status": "applied" if o.status == "active" else "undone",
                "created_at": f"{o.created_at.astimezone(zone):%d %b %Y %H:%M}",
                "undone_at": f"{o.undone_at.astimezone(zone):%d %b %Y %H:%M}" if o.undone_at else None,
            }
            for o in ops
        ],
    }
    if body.type == "pdf":
        ctx["widgets"], ctx["dashboard_filters"], ctx["answers"] = [], [], []
        row = db.scalar(select(DashboardConfiguration).where(DashboardConfiguration.session_id == sess.id))
        if body.include_dashboard and row is not None:
            config = DashboardIn.model_validate(row.configuration_json)
            tf = await _typed(sess)
            ctx["dashboard_filters"] = [_describe_filter(f) for f in config.filters]

            def run_widgets() -> list[dict[str, Any]]:
                out = []
                for w in config.widgets:
                    try:
                        q = w.query.model_copy(update={"filters": [*config.filters, *w.query.filters]})
                        res = aq.run(tf, q, sess.header_row)  # the same engine as the dashboard: figures match
                    except AppError:
                        continue  # a widget whose column was removed is left out
                    if res["kind"] in ("scatter", "table"):
                        res = {"kind": res["kind"], "meta": res["meta"]}  # not drawn in the PDF; keep it small
                    notes = []
                    m = res["meta"]
                    if m.get("measure_missing"):
                        notes.append(f"{m['measure_missing']:,} rows have no value and are not counted as zero.")
                    if m.get("measure_not_usable"):
                        notes.append(f"{m['measure_not_usable']:,} values are not numbers and are left out.")
                    if m.get("dimension_not_dated"):
                        notes.append(
                            f"{m['dimension_not_dated']:,} rows have an unclear or impossible date and are in no period."
                        )
                    out.append({"title": w.title, "chart": w.chart, "result": res, "notes": notes})
                return out

            ctx["widgets"] = await run_in_threadpool(run_widgets)
        if body.include_answers:
            rows = db.scalars(
                select(AIInteraction)
                .where(AIInteraction.session_id == sess.id, AIInteraction.operation_type.is_not(None))
                .order_by(AIInteraction.created_at.desc())
                .limit(10)
            ).all()
            ctx["answers"] = [{"question": r.question, "summary": r.result_summary} for r in reversed(rows)]
    return ctx


@router.post("/sessions/{session_id}/exports", status_code=201, dependencies=[Depends(rate_limit("export"))])
async def create_export(
    session_id: str, body: ExportIn, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from .cleaning import _ensure_current

    sess = owned_session(db, ws, session_id)
    await _ensure_current(sess)
    ctx = await _context(sess, ws, db, body)
    job_id, dataset_id, sid, version = new_id(), sess.dataset_id, sess.id, current_version(sess)
    name = f"{job_id}.{body.type}"
    path = safe_path("exports", dataset_id, name)
    file_name = _file_name(sess.dataset.original_filename, body.type)
    db.rollback()  # no transaction during the slow step

    job = ExportJob(
        id=job_id, session_id=sid, export_type=body.type, status="running", options_json={"file_name": file_name}
    )
    try:
        result = await run_in_threadpool(run_limited, export_task, body.type, dataset_id, sid, version, ctx, str(path))
        job.status, job.storage_reference = "done", f"{dataset_id}/{name}"
        job.options_json = {"file_name": file_name, "result": result, "version": version}
        job.completed_at = utcnow()
        job.expires_at = job.completed_at + FILE_TTL
    except AppError as e:
        remove(path)
        job.status, job.error = "failed", e.message
    db.add(job)
    db.add(
        AuditEvent(
            session_id=sid, event_type="export", details_json={"type": body.type, "status": job.status, "job": job_id}
        )
    )
    db.commit()
    return _out(job)


@router.get("/sessions/{session_id}/exports")
def list_exports(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    jobs = db.scalars(
        select(ExportJob).where(ExportJob.session_id == sess.id).order_by(ExportJob.created_at.desc()).limit(30)
    ).all()
    return {"exports": [_out(j) for j in jobs]}


def _owned_job(db: Session, ws: Workspace, job_id: str) -> ExportJob:
    job = db.get(ExportJob, job_id)
    if job is None:
        raise AppError(404, "NOT_FOUND", "Export not found.")
    owned_session(db, ws, job.session_id)  # 404 for other workspaces
    return job


@router.get("/exports/{job_id}/download")
def download(
    job_id: str,
    token: str = Query(max_length=200),
    ws: Workspace = Depends(current_workspace),
    db: Session = Depends(get_db),
):
    """Needs BOTH the owning workspace cookie and an unexpired signed link."""
    try:
        job = _owned_job(db, ws, job_id)
    except AppError:
        raise AppError(404, "NOT_FOUND", "Export not found.") from None
    value = unsign(token, "export") or ""
    signed_id, _, expires = value.partition(":")
    if signed_id != job.id or not expires.isdigit() or int(expires) < time.time():
        raise AppError(403, "LINK_EXPIRED", "This download link has expired. Open the Export Center for a new one.")
    if job.status != "done" or not job.storage_reference or (job.expires_at and job.expires_at < utcnow()):
        raise AppError(410, "EXPORT_GONE", "This export file is no longer available. Create it again.")
    dataset_id, _, name = job.storage_reference.partition("/")
    path = safe_path("exports", dataset_id, name)
    if not path.exists():
        raise AppError(410, "EXPORT_GONE", "This export file is no longer available. Create it again.")
    return FileResponse(
        path,
        media_type=MEDIA[job.export_type],
        filename=job.options_json.get("file_name") or name,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/exports/{job_id}", status_code=204)
def delete_export(job_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)) -> None:
    job = _owned_job(db, ws, job_id)
    if job.storage_reference:
        dataset_id, _, name = job.storage_reference.partition("/")
        remove(safe_path("exports", dataset_id, name))
    db.delete(job)
    db.commit()
