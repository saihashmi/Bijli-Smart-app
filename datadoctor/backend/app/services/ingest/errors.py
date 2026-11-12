from __future__ import annotations

from ...errors import AppError


class IngestError(AppError):
    """A file that cannot be accepted, with a user-facing explanation."""

    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(status, code, message)
