"""In-memory token-bucket rate limiting for expensive endpoints (single-process MVP; no Redis needed)."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

from fastapi import Request

from ..config import settings
from ..errors import AppError
from ..security import unsign


@dataclass(frozen=True)
class Limit:
    capacity: int  # burst size
    per_seconds: float  # time to refill the whole bucket


# Budgets per workspace (or per client address when no workspace yet).
LIMITS: dict[str, Limit] = {
    "upload": Limit(10, 60),
    "profile": Limit(30, 60),
    "clean": Limit(60, 60),
    "query": Limit(120, 60),
    "export": Limit(10, 60),
    "ai": Limit(20, 60),
    "destructive": Limit(5, 60),
}


class RateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], tuple[float, float]] = {}
        self._lock = threading.Lock()

    def hit(self, bucket: str, key: str, now: float | None = None) -> float:
        """Consume one token. Returns 0 if allowed, else seconds until the next token."""
        limit = LIMITS[bucket]
        now = time.monotonic() if now is None else now
        rate = limit.capacity / limit.per_seconds
        with self._lock:
            tokens, last = self._buckets.get((bucket, key), (float(limit.capacity), now))
            tokens = min(limit.capacity, tokens + (now - last) * rate)
            if tokens >= 1:
                self._buckets[(bucket, key)] = (tokens - 1, now)
                return 0.0
            self._buckets[(bucket, key)] = (tokens, now)
            return (1 - tokens) / rate

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


limiter = RateLimiter()


def rate_limit(bucket: str):
    """FastAPI dependency: `dependencies=[Depends(rate_limit("upload"))]`."""
    if bucket not in LIMITS:
        raise ValueError(f"Unknown rate-limit bucket {bucket}")

    def _check(request: Request) -> None:
        if not settings.rate_limits_enabled:
            return
        key = unsign(request.cookies.get(settings.workspace_cookie), "workspace") or (
            request.client.host if request.client else "unknown"
        )
        wait = limiter.hit(bucket, key)
        if wait > 0:
            retry = max(1, math.ceil(wait))
            raise AppError(
                429,
                "RATE_LIMITED",
                f"Too many requests. Please wait {retry} s and try again.",
                headers={"Retry-After": str(retry)},
            )

    return _check
