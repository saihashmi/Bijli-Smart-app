"""Reject oversized uploads before the body is read into the server (pure ASGI middleware)."""

from __future__ import annotations

import json

from ..config import settings
from ..errors import error_body

MULTIPART_OVERHEAD = 64 * 1024
# After deciding to reject, keep reading (and discarding) up to this much more of the body so that proxies
# such as Next.js receive a clean 413 instead of a reset connection. Larger bodies are cut off.
DRAIN_LIMIT = 64 * 1024 * 1024


class _TooLarge(Exception):
    pass


class UploadSizeLimitMiddleware:
    def __init__(self, app, path: str = "/api/uploads"):
        self.app, self.path = app, path

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != self.path or scope["method"] != "POST":
            return await self.app(scope, receive, send)

        limit = settings.max_upload_mb * 1024 * 1024 + MULTIPART_OVERHEAD
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await self._drain(receive, int(declared))
            return await self._reject(send)

        received = 0
        response_started = False

        async def counting_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge
            return message

        async def tracking_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not response_started:
                await self._drain(receive, int(declared) if declared and declared.isdigit() else DRAIN_LIMIT)
                await self._reject(send)

    @staticmethod
    async def _drain(receive, declared: int) -> None:
        if declared > DRAIN_LIMIT:
            return
        while True:
            message = await receive()
            if message["type"] != "http.request" or not message.get("more_body", False):
                return

    @staticmethod
    async def _reject(send):
        body = json.dumps(
            error_body("FILE_TOO_LARGE", f"The file is larger than the {settings.max_upload_mb} MB limit.")
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"connection", b"close")],
            }
        )
        await send({"type": "http.response.body", "body": body})
