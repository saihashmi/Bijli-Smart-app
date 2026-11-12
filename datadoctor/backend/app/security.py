"""Server secret and HMAC signing for the workspace cookie (and, later, download links)."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from functools import lru_cache

from .config import settings


@lru_cache(maxsize=1)
def secret_key() -> bytes:
    """SECRET_KEY from the environment, or a random key generated once and kept in storage (mode 0600)."""
    if settings.secret_key:
        return settings.secret_key.encode()
    path = settings.storage_dir / ".secret_key"
    if not path.exists():
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_urlsafe(48))
    return path.read_text().strip().encode()


def sign(value: str, purpose: str) -> str:
    mac = hmac.new(secret_key(), f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()[:40]
    return f"{value}.{mac}"


def unsign(token: str | None, purpose: str) -> str | None:
    if not token or "." not in token:
        return None
    value, _, mac = token.rpartition(".")
    expected = sign(value, purpose).rpartition(".")[2]
    return value if hmac.compare_digest(mac, expected) else None
