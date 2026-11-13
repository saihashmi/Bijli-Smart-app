"""AI Analyst API (SPEC FR-5, §12). A question can only ever select one allowlisted operation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..errors import AppError
from ..middleware.ratelimit import rate_limit
from ..middleware.workspace import current_workspace, owned_session
from ..models import AIInteraction, Workspace
from ..schemas.settings import Preferences
from ..services.analyst import ops, provider
from ..services.analyst.interpret import interpret
from ..services.analyst.verify import verify
from ..services.analytics.typed import TypedFrame
from .analytics import _typed
from .sessions import get_profile

router = APIRouter(prefix="/api", tags=["analyst"])

LIMITATIONS = [
    "A question is matched to one of a fixed list of calculations. It can be misread, so the calculation and its settings are always shown.",
    "The assistant cannot see your rows. It cannot forecast, and it cannot answer questions outside the listed calculations.",
    "Figures come from the calculation on your data. Any AI-written explanation is checked against them and discarded if it adds anything.",
]

# What each operation's form needs (drives the guided builder). role: which columns may be chosen.
FORMS: dict[str, list[dict[str, Any]]] = {
    "count_rows": [],
    "aggregate": [{"name": "measure", "role": "any"}, {"name": "agg", "role": "agg"}],
    "group_rank": [
        {"name": "group_by", "role": "group"},
        {"name": "measure", "role": "any", "optional": True},
        {"name": "agg", "role": "agg"},
        {"name": "order", "role": "order"},
        {"name": "top_n", "role": "int"},
    ],
    "time_trend": [
        {"name": "date_col", "role": "date"},
        {"name": "grain", "role": "grain"},
        {"name": "measure", "role": "any", "optional": True},
        {"name": "agg", "role": "agg"},
    ],
    "extreme_period": [
        {"name": "date_col", "role": "date"},
        {"name": "grain", "role": "grain"},
        {"name": "measure", "role": "any", "optional": True},
        {"name": "agg", "role": "agg"},
        {"name": "which", "role": "which"},
    ],
    "compare_groups": [
        {"name": "group_by", "role": "group"},
        {"name": "values", "role": "values"},
        {"name": "measure", "role": "any", "optional": True},
        {"name": "agg", "role": "agg"},
    ],
    "distribution": [{"name": "column", "role": "number"}],
    "correlation": [{"name": "x", "role": "number"}, {"name": "y", "role": "number"}],
    "missing_summary": [],
    "duplicate_summary": [{"name": "key_columns", "role": "columns", "optional": True}],
    "column_profile": [{"name": "column", "role": "any"}],
    "outlier_summary": [{"name": "column", "role": "number"}],
    "chart_suggestions": [],
    "quality_explain": [],
}


class AskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str | None = Field(default=None, min_length=1, max_length=500)
    operation: str | None = Field(default=None, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _one_of(self) -> AskIn:
        if not self.question and not self.operation:
            raise ValueError("send a question or an operation")
        return self


@router.get("/analyst/operations")
def list_operations() -> dict[str, Any]:
    return {
        "operations": [
            {"id": k, "title": v["title"], "example": v["example"], "fields": FORMS[k]}
            for k, v in ops.OPERATIONS.items()
        ],
        "limitations": LIMITATIONS,
        "ai": {
            "configured": settings.ai_configured,
            "provider": "groq" if settings.ai_configured else None,
            "model": settings.groq_model if settings.ai_configured else None,
        },
    }


def _suggestions(tf: TypedFrame, sensitive: list[str]) -> list[dict[str, Any]]:
    cols = [tf.col(n) for n in tf.columns if n not in sensitive]
    numeric = sorted((c for c in cols if c.kind == "number" and c.unique > 1), key=lambda c: -c.unique)
    dates = [c for c in cols if c.kind == "date"]
    cats = [c for c in cols if c.kind in ("category", "boolean") and 2 <= c.unique <= 50]
    out: list[dict[str, Any]] = [{"question": "How many rows are there?", "operation": "count_rows", "params": {}}]
    if numeric:
        m = numeric[0].name
        out.append(
            {"question": f"What is the total of {m}?", "operation": "aggregate", "params": {"measure": m, "agg": "sum"}}
        )
        if cats:
            g = cats[0].name
            out.append(
                {
                    "question": f"Which {g} has the highest total {m}?",
                    "operation": "group_rank",
                    "params": {"group_by": g, "measure": m, "agg": "sum"},
                }
            )
        if dates:
            d = dates[0].name
            out.append(
                {
                    "question": f"Show the monthly trend of {m}.",
                    "operation": "time_trend",
                    "params": {"date_col": d, "grain": "month", "measure": m, "agg": "sum"},
                }
            )
        out.append({"question": f"How is {m} distributed?", "operation": "distribution", "params": {"column": m}})
        if len(numeric) > 1:
            out.append(
                {
                    "question": f"Is {numeric[1].name} related to {m}?",
                    "operation": "correlation",
                    "params": {"x": numeric[1].name, "y": m},
                }
            )
    elif cats:
        g = cats[0].name
        out.append({"question": f"Which {g} has the most rows?", "operation": "group_rank", "params": {"group_by": g}})
    out += [
        {"question": "Which columns contain missing values?", "operation": "missing_summary", "params": {}},
        {"question": "Are there duplicate rows?", "operation": "duplicate_summary", "params": {}},
        {"question": "Why is my data health score what it is?", "operation": "quality_explain", "params": {}},
    ]
    return out[:8]


@router.get("/sessions/{session_id}/analyst/suggestions", dependencies=[Depends(rate_limit("query"))])
async def suggestions(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    tf = await _typed(sess)
    return {"suggestions": await run_in_threadpool(_suggestions, tf, list(sess.sensitive_columns_json or []))}


def _ai_columns(tf: TypedFrame, sensitive: list[str], share_names: bool) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Column list for the provider: sensitive columns are never included; names become aliases when not shared."""
    listed, back = [], {}
    for i, name in enumerate(tf.columns, start=1):
        if name in sensitive:
            continue
        shown = name if share_names else f"col_{i}"
        back[shown] = name
        listed.append({"name": shown, "type": tf.col(name).kind})
    return listed, back


def _unalias(params: dict[str, Any], back: dict[str, str]) -> dict[str, Any]:
    def fix(v: Any) -> Any:
        if isinstance(v, str):
            return back.get(v, v)
        if isinstance(v, list):
            return [fix(x) for x in v]
        if isinstance(v, dict):
            return {k: fix(x) for k, x in v.items()}
        return v

    return {k: (v if k == "values" else fix(v)) for k, v in params.items()}


@router.post("/sessions/{session_id}/analyst/ask", dependencies=[Depends(rate_limit("ai"))])
async def ask(
    session_id: str, body: AskIn, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    sensitive = list(sess.sensitive_columns_json or [])
    prefs = Preferences(**(ws.settings_json or {}))
    tf = await _typed(sess)
    profile = await get_profile(session_id, ws, db)
    sid = sess.id
    db.rollback()

    question = (body.question or "").strip()
    notices: list[str] = []
    interpreter = "guided"
    op, params = body.operation, body.params
    reason: str | None = None

    def work() -> dict[str, Any]:
        nonlocal op, params, interpreter, reason
        if op is None:
            interpreter = "local"
            if settings.ai_configured:
                try:
                    listed, back = _ai_columns(tf, sensitive, prefs.ai_share_column_names)
                    chosen, chosen_params = provider.choose_operation(question, listed)
                    if chosen:
                        op, params, interpreter = chosen, _unalias(chosen_params, back), "groq"
                except provider.ProviderError:
                    notices.append("The AI service was unavailable, so the built-in interpreter was used instead.")
            if op is None:
                found = interpret(question, tf, sensitive)
                op, params, reason = found.operation, found.params, found.reason
        if op is None:
            return {}
        try:
            validated = ops.validate(op, params)
            return ops.execute(op, validated, tf, profile, sensitive)
        except AppError as e:
            if e.status != 422:
                raise
            if interpreter == "groq":  # the model chose something that does not fit: try the local rules instead
                found = interpret(question, tf, sensitive)
                if found.operation:
                    try:
                        op, params, interpreter = found.operation, found.params, "local"
                        notices.append(
                            "The AI suggestion did not fit this data, so the built-in interpreter was used instead."
                        )
                        return ops.execute(op, ops.validate(op, params), tf, profile, sensitive)
                    except AppError as e2:
                        reason = e2.message
                        return {}
            reason = e.message
            return {}

    answer = await run_in_threadpool(work)

    explanation: dict[str, Any] | None = None
    status = "none"
    if answer and settings.ai_configured:
        used = set(ops.columns_used(op or "", ops.validate(op or "", answer["params"])))
        if used & set(sensitive):
            notices.append("This answer uses a column marked as sensitive, so nothing was sent to the AI service.")
        elif not prefs.ai_share_column_names:
            notices.append(
                "Column names are not shared with the AI service (Settings), so no AI explanation was requested."
            )
        else:
            try:
                text = await run_in_threadpool(
                    provider.explain, question or answer["title"], answer["answer"], answer["table"]
                )
                ok, why = verify(text, answer)
                status = "verified" if ok else "rejected"
                if ok:
                    explanation = {"text": text, "provider": "groq", "model": settings.groq_model, "status": "verified"}
                else:
                    notices.append(
                        "The AI explanation mentioned something that is not in the computed result, so it was discarded "
                        f"({why}). The explanation shown is the built-in one."
                    )
            except provider.ProviderError:
                notices.append("The AI service was unavailable, so the built-in explanation is shown.")

    record = AIInteraction(
        session_id=sid,
        question=question or (ops.OPERATIONS[op]["title"] if op in ops.OPERATIONS else ""),
        operation_type=op if answer else None,
        parameters_json=answer["params"] if answer else {},
        result_summary=answer["answer"] if answer else (reason or ""),
        provider="groq" if interpreter == "groq" or explanation else "local",
        explanation_status=status,
    )
    db.add(record)
    db.commit()

    if not answer:
        tips = await run_in_threadpool(_suggestions, tf, sensitive)
        return {
            "id": record.id,
            "status": "cannot_answer",
            "question": question,
            "interpreter": interpreter,
            "message": reason or "I can't answer that with this data or the supported operations.",
            "alternatives": tips[:4],
            "notices": notices,
            "answer": None,
            "explanation": None,
        }
    return {
        "id": record.id,
        "status": "answered",
        "question": question,
        "interpreter": interpreter,
        "answer": answer,
        "explanation": explanation,
        "notices": notices,
        "alternatives": [],
        "message": None,
    }


@router.get("/sessions/{session_id}/analyst/history")
def history(
    session_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)
) -> dict[str, Any]:
    sess = owned_session(db, ws, session_id)
    rows = db.scalars(
        select(AIInteraction)
        .where(AIInteraction.session_id == sess.id)
        .order_by(AIInteraction.created_at.desc())
        .limit(50)
    ).all()
    return {
        "interactions": [
            {
                "id": r.id,
                "question": r.question,
                "operation": r.operation_type,
                "params": r.parameters_json,
                "summary": r.result_summary,
                "provider": r.provider,
                "explanation_status": r.explanation_status,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }
