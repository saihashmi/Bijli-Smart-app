"""One error shape for every failure: {"error": {"code", "message", "id"}}. Never leaks stack traces."""

from __future__ import annotations

import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("datadoctor.errors")


class AppError(Exception):
    """An expected, user-facing error with a stable machine-readable code."""

    def __init__(self, status: int, code: str, message: str, headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.headers = status, code, message, headers


def _error_id() -> str:
    return f"err_{secrets.token_hex(6)}"


def error_body(code: str, message: str, error_id: str | None = None) -> dict:
    return {"error": {"code": code, "message": message, "id": error_id or _error_id()}}


_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "INVALID_INPUT",
    429: "RATE_LIMITED",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            error_body(code, message), status_code=exc.status_code, headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        # Report which fields are wrong without echoing submitted values back.
        problems = []
        for err in exc.errors()[:10]:
            loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
            problems.append(f"{loc}: {err.get('msg', 'invalid')}" if loc else err.get("msg", "invalid"))
        return JSONResponse(error_body("INVALID_INPUT", "; ".join(problems) or "Invalid input."), status_code=422)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        error_id = _error_id()
        # Log type and location only; exception messages can contain cell values.
        log.error(
            "unhandled %s on %s %s [%s]",
            type(exc).__name__,
            request.method,
            request.url.path,
            error_id,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            error_body("INTERNAL_ERROR", "Something went wrong on the server. Please try again.", error_id),
            status_code=500,
        )
