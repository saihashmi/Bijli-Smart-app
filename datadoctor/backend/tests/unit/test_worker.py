import time

import pytest

from app.errors import AppError
from app.worker import run_limited

from . import worker_tasks as t


def test_returns_result():
    assert run_limited(t.add, 2, 3) == 5


def test_timeout_kills_the_child():
    start = time.monotonic()
    with pytest.raises(AppError) as exc:
        run_limited(t.sleepy, 30, timeout=2)
    assert exc.value.code == "PROCESSING_TIMEOUT"
    assert time.monotonic() - start < 10


def test_unexpected_errors_are_generic():
    with pytest.raises(AppError) as exc:
        run_limited(t.explode)
    assert exc.value.code == "PROCESSING_FAILED"
    assert "secret" not in exc.value.message


def test_app_errors_pass_through():
    with pytest.raises(AppError) as exc:
        run_limited(t.friendly_failure)
    assert (exc.value.status, exc.value.code) == (422, "BAD_SHEET")


def test_memory_cap_is_enforced():
    with pytest.raises(AppError) as exc:
        run_limited(t.hog_memory, memory_mb=400, timeout=30)
    assert exc.value.code in ("PROCESSING_OUT_OF_MEMORY", "PROCESSING_FAILED")
