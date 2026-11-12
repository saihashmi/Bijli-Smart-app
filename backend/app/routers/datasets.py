from __future__ import annotations

import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings as app_settings
from ..db import get_session
from ..models import Dataset, Job
from ..schemas import CleanIn, ConfigIn, DatasetOut, JobOut
from ..services import analysis as analysis_svc
from ..services import cleaning, ingest, insights, reports, store
from ..services.jsonutil import jsonable

router = APIRouter(prefix="/api", tags=["datasets"])

DEFAULT_SETTINGS = {"currency": app_settings.default_currency, "tariff_per_kwh": None, "peak_start_hour": 18,
                    "peak_end_hour": 22, "reduction_target_pct": 10}


@contextmanager
def job(db: Session, kind: str, dataset_id: str | None):
    j = Job(kind=kind, dataset_id=dataset_id, status="running", details={})
    db.add(j)
    db.commit()
    t0 = time.perf_counter()
    try:
        yield j
        j.status = "success"
    except HTTPException as e:
        j.status, j.message = "failed", str(e.detail)
        raise
    except Exception as e:
        j.status, j.message = "failed", str(e)
        raise
    finally:
        j.finished_at = datetime.now(timezone.utc)
        j.details = {**(j.details or {}), "duration_ms": round((time.perf_counter() - t0) * 1000)}
        db.commit()


def _get(db: Session, dataset_id: str) -> Dataset:
    ds = db.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(404, "Dataset not found")
    return ds


def _raw(ds: Dataset) -> pd.DataFrame:
    return store.load(store.raw_frame_path(ds.id))


def _analysis_frame(ds: Dataset) -> tuple[pd.DataFrame, str]:
    errors = ingest.validate_mapping(_raw(ds), ds.mapping)
    if errors:
        raise HTTPException(422, " ".join(errors))
    if ds.cleaned_path and Path(ds.cleaned_path).exists():
        return store.load(ds.cleaned_path), "cleaned"
    return cleaning.minimal_typed(_raw(ds), ds.mapping), "raw"


def _compute(ds: Dataset) -> dict[str, Any]:
    df, stage = _analysis_frame(ds)
    result = analysis_svc.analyze(df, ds.mapping, ds.settings or DEFAULT_SETTINGS)
    result["data_stage"] = stage
    return result


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "ai_enabled": app_settings.ai_enabled,
            "ai_model": app_settings.groq_model if app_settings.ai_enabled else None}


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_session)):
    return db.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all()


@router.post("/datasets", response_model=DatasetOut, status_code=201)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_session)):
    filename = Path(file.filename or "upload").name
    ext = Path(filename).suffix.lower()
    if ext not in ingest.SUPPORTED_EXTENSIONS:
        raise HTTPException(415, "Upload a .csv or .xlsx file.")
    with job(db, "upload", None) as j:
        ds = Dataset(name=re.sub(r"\.[^.]+$", "", filename)[:255] or "Dataset", original_filename=filename,
                     file_type=ingest.SUPPORTED_EXTENSIONS[ext], raw_path="")
        db.add(ds)
        db.flush()
        dest = app_settings.upload_dir / f"{ds.id}{ext}"
        limit = app_settings.max_upload_mb * 1024 * 1024
        size = 0
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    out.close()
                    dest.unlink(missing_ok=True)
                    db.rollback()
                    raise HTTPException(413, f"File is larger than {app_settings.max_upload_mb} MB.")
                out.write(chunk)
        try:
            df = ingest.read_table(dest)
        except ingest.IngestError as e:
            dest.unlink(missing_ok=True)
            db.rollback()
            raise HTTPException(422, str(e)) from e
        if df.empty:
            dest.unlink(missing_ok=True)
            db.rollback()
            raise HTTPException(422, "The file has no data rows.")
        store.save(df, store.raw_frame_path(ds.id))
        ds.raw_path = str(dest)
        ds.rows_raw = len(df)
        ds.columns = list(df.columns)
        ds.mapping = ingest.detect_mapping(df, app_settings.default_dayfirst)
        ds.settings = dict(DEFAULT_SETTINGS)
        j.dataset_id = ds.id
        j.message = f"Uploaded {filename} ({len(df)} rows, {df.shape[1]} columns)"
        j.details = {"rows": len(df), "columns": df.shape[1], "bytes": size, "detected_mapping": ds.mapping}
        db.commit()
    db.refresh(ds)
    return ds


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: str, db: Session = Depends(get_session)):
    return _get(db, dataset_id)


@router.patch("/datasets/{dataset_id}", response_model=DatasetOut)
def configure(dataset_id: str, body: ConfigIn, db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    if body.name:
        ds.name = body.name
    if body.mapping is not None:
        mapping = {**ds.mapping, **body.mapping.model_dump()}
        errors = ingest.validate_mapping(_raw(ds), mapping)
        if errors:
            raise HTTPException(422, " ".join(errors))
        if any(mapping.get(k) != ds.mapping.get(k) for k in ("timestamp", "consumption", "cost", "category", "dayfirst")):
            # Column roles changed: the previous cleaned version no longer matches.
            store.remove(ds.cleaned_path)
            ds.cleaned_path, ds.rows_clean, ds.cleaning_log, ds.status = None, None, [], "uploaded"
        ds.mapping = mapping
    if body.settings is not None:
        ds.settings = body.settings.model_dump()
    db.commit()
    return ds


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    store.remove(ds.raw_path, ds.cleaned_path, store.raw_frame_path(ds.id))
    db.delete(ds)
    db.commit()
    return Response(status_code=204)


@router.get("/datasets/{dataset_id}/profile")
def get_profile(dataset_id: str, db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    return jsonable(cleaning.profile(_raw(ds), ds.mapping))


@router.post("/datasets/{dataset_id}/cleaning-advice")
def get_cleaning_advice(dataset_id: str, db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    with job(db, "cleaning_advice", ds.id) as j:
        prof = jsonable(cleaning.profile(_raw(ds), ds.mapping))
        advice = insights.cleaning_advice(prof)
        j.message = f"Cleaning advice ({advice['source']})"
        j.details = {"source": advice["source"], "removed_statements": len(advice.get("removed", []))}
    return advice


@router.post("/datasets/{dataset_id}/clean", response_model=DatasetOut)
def clean(dataset_id: str, body: CleanIn, db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    raw = _raw(ds)
    errors = ingest.validate_mapping(raw, ds.mapping)
    if errors:
        raise HTTPException(422, " ".join(errors))
    with job(db, "clean", ds.id) as j:
        try:
            out, log = cleaning.apply(raw, ds.mapping, body.actions)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        ds.cleaned_path = store.save(out, store.clean_frame_path(ds.id))
        ds.rows_clean = len(out)
        ds.cleaning_log = jsonable(log)
        ds.status = "cleaned"
        j.message = f"Cleaned: {len(raw)} → {len(out)} rows"
        j.details = {"actions": body.actions, "rows_before": len(raw), "rows_after": len(out)}
    db.commit()
    return ds


@router.delete("/datasets/{dataset_id}/clean", response_model=DatasetOut)
def reset_clean(dataset_id: str, db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    store.remove(ds.cleaned_path)
    ds.cleaned_path, ds.rows_clean, ds.cleaning_log, ds.status = None, None, [], "uploaded"
    db.commit()
    return ds


@router.get("/datasets/{dataset_id}/preview")
def preview(dataset_id: str, stage: str = Query("raw", pattern="^(raw|clean)$"),
            limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
            db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    if stage == "clean":
        if not ds.cleaned_path:
            raise HTTPException(404, "This dataset has not been cleaned yet.")
        df = store.load(ds.cleaned_path)
    else:
        df = _raw(ds)
    page = df.iloc[offset: offset + limit]
    return {"stage": stage, "total": len(df), "offset": offset, "columns": list(map(str, df.columns)),
            "rows": [[jsonable(v) for v in row] for row in page.itertuples(index=False)]}


@router.get("/datasets/{dataset_id}/analysis")
def get_analysis(dataset_id: str, db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    with job(db, "analyze", ds.id) as j:
        result = _compute(ds)
        j.message = f"Analysed {result.get('summary', {}).get('records', 0)} records ({result['data_stage']} data)"
    return result


@router.post("/datasets/{dataset_id}/insights")
def get_insights(dataset_id: str, use_ai: bool = True, db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    with job(db, "insights", ds.id) as j:
        result = _compute(ds)
        out = insights.insights(result, use_ai=use_ai)
        out["data_stage"] = result["data_stage"]
        j.message = f"Insights generated ({out['source']})"
        j.details = {"source": out["source"], "removed_statements": len(out.get("removed", [])),
                     **({"ai_error": out["ai_error"]} if out.get("ai_error") else {})}
    return out


@router.get("/datasets/{dataset_id}/export")
def export(dataset_id: str, format: str = Query("xlsx", pattern="^(xlsx|pdf)$"), use_ai: bool = False,
           db: Session = Depends(get_session)):
    ds = _get(db, dataset_id)
    with job(db, "export", ds.id) as j:
        df, stage = _analysis_frame(ds)
        result = analysis_svc.analyze(df, ds.mapping, ds.settings or DEFAULT_SETTINGS)
        ins = insights.insights(result, use_ai=use_ai)
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", ds.name).strip("_") or "report"
        if format == "xlsx":
            content = reports.build_xlsx(ds.name, result, ins, df, ds.cleaning_log)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            content = reports.build_pdf(ds.name, result, ins, ds.cleaning_log)
            media = "application/pdf"
        j.message = f"Exported {format.upper()} ({stage} data)"
        j.details = {"format": format, "bytes": len(content), "insight_source": ins["source"]}
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="bijli-{safe}.{format}"'})


@router.get("/datasets/{dataset_id}/jobs", response_model=list[JobOut])
def dataset_jobs(dataset_id: str, db: Session = Depends(get_session)):
    _get(db, dataset_id)
    return db.scalars(select(Job).where(Job.dataset_id == dataset_id).order_by(Job.id.desc()).limit(200)).all()


@router.get("/jobs", response_model=list[JobOut])
def all_jobs(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_session)):
    return db.scalars(select(Job).order_by(Job.id.desc()).limit(limit)).all()
