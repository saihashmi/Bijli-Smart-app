"""Analytics API: one query engine for dashboards, the AI Analyst and exports (SPEC FR-4, §12.4)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import AppError
from ..middleware.ratelimit import rate_limit
from ..middleware.workspace import current_workspace, owned_session
from ..models import AnalysisSession, DashboardConfiguration, Workspace
from ..services.analytics import query as aq
from ..services.analytics.recommend import fields, recommend
from ..services.analytics.typed import TypedFrame, typed
from ..services.storage import snapshots
from .cleaning import _ensure_current
from .sessions import current_version

router = APIRouter(prefix="/api", tags=["analytics"])

MAX_BATCH = 16


class QueryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    queries: list[aq.Query] = Field(min_length=1, max_length=MAX_BATCH)
    filters: list[aq.Filter] = Field(default_factory=list, max_length=20)  # dashboard-wide, added to every query


class Widget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=120)
    chart: Literal["kpi", "bar", "line", "area", "pie", "donut", "histogram", "scatter", "table"]
    query: aq.Query
    width: Literal[3, 4, 6, 8, 12] = 6
    reason: str | None = Field(default=None, max_length=400)


class DashboardIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: Literal["midnight", "executive", "minimal"] = "executive"
    filters: list[aq.Filter] = Field(default_factory=list, max_length=20)
    widgets: list[Widget] = Field(default_factory=list, max_length=24)


CHART_NEEDS = {
    "kpi": "aggregate",
    "bar": "aggregate",
    "line": "aggregate",
    "area": "aggregate",
    "pie": "aggregate",
    "donut": "aggregate",
    "histogram": "histogram",
    "scatter": "scatter",
    "table": "table",
}


async def _typed(sess: AnalysisSession) -> TypedFrame:
    await _ensure_current(sess)
    df = await run_in_threadpool(snapshots.load, sess.dataset_id, sess.id, current_version(sess))
    return typed(df)


@router.get("/sessions/{session_id}/analytics/fields", dependencies=[Depends(rate_limit("query"))])
async def get_fields(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Columns with their kind and what each can be used for, so the UI only offers valid combinations."""
    sess = owned_session(db, ws, session_id)
    tf = await _typed(sess)
    cols = await run_in_threadpool(fields, tf, list(sess.sensitive_columns_json or []))
    return {
        "version": current_version(sess),
        "rows": len(tf),
        "fields": cols,
        "aggregations": [{"id": k, "label": v} for k, v in aq.AGG_LABEL.items()],
        "grains": ["day", "week", "month", "quarter", "year"],
        "limits": {"points": aq.MAX_POINTS, "series": aq.MAX_SERIES, "scatter_sample": aq.SCATTER_SAMPLE},
    }


@router.post("/sessions/{session_id}/analytics/query", dependencies=[Depends(rate_limit("query"))])
async def run_queries(
    session_id: str, body: QueryBatch, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Run up to 16 queries against the current data. One failing query does not fail the others."""
    sess = owned_session(db, ws, session_id)
    tf = await _typed(sess)
    header_row, version = sess.header_row, current_version(sess)
    db.rollback()

    def work() -> list[dict[str, Any]]:
        out = []
        for q in body.queries:
            full = q.model_copy(update={"filters": [*body.filters, *q.filters]})
            try:
                out.append({"ok": True, "result": aq.run(tf, full, header_row)})
            except AppError as e:
                out.append({"ok": False, "error": {"code": e.code, "message": e.message}})
        return out

    return {"version": version, "results": await run_in_threadpool(work)}


@router.get("/sessions/{session_id}/analytics/recommendations", dependencies=[Depends(rate_limit("query"))])
async def get_recommendations(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    tf = await _typed(sess)
    return await run_in_threadpool(recommend, tf, list(sess.sensitive_columns_json or []))


def _columns_used(q: Any) -> list[str]:
    used = [f.column for f in q.filters]
    if isinstance(q, aq.AggregateQuery):
        used += [c for c in (q.measure.column, q.dimension.column if q.dimension else None, q.series) if c]
    elif isinstance(q, aq.HistogramQuery):
        used.append(q.column)
    elif isinstance(q, aq.ScatterQuery):
        used += [q.x, q.y]
    else:
        used += q.columns
    return used


@router.get("/sessions/{session_id}/dashboard")
async def get_dashboard(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """The saved dashboard, or `saved: false` with nothing invented. Widgets whose columns are gone are listed."""
    sess = owned_session(db, ws, session_id)
    row = db.scalar(select(DashboardConfiguration).where(DashboardConfiguration.session_id == sess.id))
    if row is None:
        return {"saved": False, "dashboard": None, "updated_at": None, "broken_widgets": []}
    config = DashboardIn.model_validate(row.configuration_json)
    tf = await _typed(sess)
    broken = []
    for w in config.widgets:
        gone = sorted({c for c in _columns_used(w.query) if not tf.has(c)})
        if gone:
            broken.append({"id": w.id, "missing_columns": gone})
    return {
        "saved": True,
        "dashboard": config.model_dump(mode="json"),
        "updated_at": row.updated_at,
        "broken_widgets": broken,
    }


@router.put("/sessions/{session_id}/dashboard")
async def put_dashboard(
    session_id: str, body: DashboardIn, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    ids = [w.id for w in body.widgets]
    if len(set(ids)) != len(ids):
        raise AppError(422, "DUPLICATE_WIDGET_ID", "Two widgets share the same id.")
    for w in body.widgets:
        if w.query.kind != CHART_NEEDS[w.chart]:
            raise AppError(422, "CHART_QUERY_MISMATCH", f"A {w.chart} chart cannot show a {w.query.kind} query.")
    row = db.scalar(select(DashboardConfiguration).where(DashboardConfiguration.session_id == sess.id))
    data = body.model_dump(mode="json")
    if row is None:
        row = DashboardConfiguration(session_id=sess.id, configuration_json=data)
        db.add(row)
    else:
        row.configuration_json = data
    db.commit()
    db.refresh(row)
    return {"saved": True, "dashboard": data, "updated_at": row.updated_at, "broken_widgets": []}


@router.delete("/sessions/{session_id}/dashboard", status_code=204)
def delete_dashboard(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> None:
    sess = owned_session(db, ws, session_id)
    row = db.scalar(select(DashboardConfiguration).where(DashboardConfiguration.session_id == sess.id))
    if row is not None:
        db.delete(row)
        db.commit()
