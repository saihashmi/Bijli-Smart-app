"""Baseline security headers on every API response."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-resource-policy", b"same-origin"),
]
NO_STORE = (b"cache-control", b"no-store")  # responses contain the user's data; nothing should cache them


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers += [h for h in HEADERS if h[0] not in present]
                if b"cache-control" not in present:
                    headers.append(NO_STORE)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
