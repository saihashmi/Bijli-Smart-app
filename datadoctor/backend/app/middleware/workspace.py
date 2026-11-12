"""Workspace ownership for local mode (SPEC D2).

A browser gets a random workspace id in an HttpOnly, SameSite=Lax cookie signed with the server secret.
It keeps datasets of different browsers apart. It is NOT user authentication and must not be treated as such.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..errors import AppError
from ..models import AnalysisSession, Dataset, Workspace, utcnow
from ..security import sign, unsign

COOKIE_PURPOSE = "workspace"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365
_TOUCH_INTERVAL = timedelta(minutes=5)


def _set_cookie(response: Response, workspace_id: str) -> None:
    response.set_cookie(
        settings.workspace_cookie,
        sign(workspace_id, COOKIE_PURPOSE),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def current_workspace(request: Request, response: Response, db: Session = Depends(get_db)) -> Workspace:
    """Return the caller's workspace, creating one (and setting the cookie) on first use."""
    workspace_id = unsign(request.cookies.get(settings.workspace_cookie), COOKIE_PURPOSE)
    ws = db.get(Workspace, workspace_id) if workspace_id else None
    if ws is None:
        ws = Workspace(settings_json={})
        db.add(ws)
        db.commit()
        _set_cookie(response, ws.id)
    else:
        now = utcnow()
        last = ws.last_seen_at if ws.last_seen_at.tzinfo else ws.last_seen_at.replace(tzinfo=now.tzinfo)
        if now - last > _TOUCH_INTERVAL:
            ws.last_seen_at = now
            db.commit()
    return ws


def owned_dataset(db: Session, workspace: Workspace, dataset_id: str) -> Dataset:
    """Fetch a dataset only if it belongs to this workspace. Otherwise 404, never revealing that it exists."""
    ds = db.get(Dataset, dataset_id)
    if ds is None or ds.workspace_id != workspace.id or ds.status == "deleted":
        raise AppError(404, "NOT_FOUND", "Dataset not found.")
    return ds


def owned_session(db: Session, workspace: Workspace, session_id: str) -> AnalysisSession:
    sess = db.get(AnalysisSession, session_id)
    if sess is None or sess.dataset.workspace_id != workspace.id or sess.status == "expired":
        raise AppError(404, "NOT_FOUND", "Analysis session not found.")
    return sess
