"""Module-level functions for worker tests (spawned processes must be able to import them)."""

import time

from app.errors import AppError


def add(a, b):
    return a + b


def sleepy(seconds):
    time.sleep(seconds)
    return "done"


def explode():
    raise ValueError("secret cell value")


def friendly_failure():
    raise AppError(422, "BAD_SHEET", "Explained to the user.")


def hog_memory():
    blocks = []
    while True:
        blocks.append(bytearray(64 * 1024 * 1024))


def slow_parse(*args, **kwargs):
    """parse_to_snapshot, but slower than SQLite's default 5 s lock timeout."""
    from app.services.ingest.parse import parse_to_snapshot

    time.sleep(6)
    return parse_to_snapshot(*args, **kwargs)
