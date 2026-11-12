"""Run heavy work (parsing, profiling, exports) in a separate process with a time limit and a memory cap.

Why: a huge or malformed spreadsheet must not freeze or crash the web server. The child process is
started fresh ("spawn"), limited with RLIMIT_AS on Linux, and killed if it exceeds the time limit.
Only small results travel back; large data is written to storage by the task itself.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import traceback
from collections.abc import Callable
from typing import Any

from .config import settings
from .errors import AppError

log = logging.getLogger("datadoctor.worker")
_ctx = mp.get_context("spawn")


def _child(conn, fn: Callable[..., Any], args: tuple, kwargs: dict, memory_mb: int) -> None:
    try:
        if memory_mb > 0:
            try:
                import resource

                limit = memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            except (ImportError, ValueError, OSError):  # non-Linux or not permitted: run without the cap
                pass
        result = fn(*args, **kwargs)
        conn.send(("ok", result))
    except AppError as e:
        conn.send(("app_error", (e.status, e.code, e.message)))
    except MemoryError:
        conn.send(("memory", None))
    except BaseException as e:  # noqa: BLE001 - report every failure back to the parent
        conn.send(("error", (type(e).__name__, traceback.format_exc(limit=8))))
    finally:
        conn.close()


def run_limited(
    fn: Callable[..., Any], *args: Any, timeout: float | None = None, memory_mb: int | None = None, **kwargs: Any
) -> Any:
    """Call fn(*args, **kwargs) in a child process. fn must be importable (module-level)."""
    timeout = settings.process_timeout_s if timeout is None else timeout
    memory_mb = settings.worker_memory_mb if memory_mb is None else memory_mb
    parent, child = _ctx.Pipe(duplex=False)
    proc = _ctx.Process(target=_child, args=(child, fn, args, kwargs, memory_mb), daemon=True)
    proc.start()
    child.close()
    try:
        if not parent.poll(timeout):
            raise AppError(
                504,
                "PROCESSING_TIMEOUT",
                f"Processing took longer than the {int(timeout)}-second limit. Try a smaller file or sheet.",
            )
        try:
            status, payload = parent.recv()
        except EOFError:
            status, payload = "crashed", None
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join(5)
        parent.close()

    if status == "ok":
        return payload
    if status == "app_error":
        code_status, code, message = payload
        raise AppError(code_status, code, message)
    if status == "memory":
        raise AppError(
            507,
            "PROCESSING_OUT_OF_MEMORY",
            "This sheet needs more memory than the server allows. Try a smaller file, or remove unused columns.",
        )
    if status == "error":
        name, tb = payload
        log.error("worker task %s failed with %s\n%s", getattr(fn, "__name__", fn), name, tb)
    else:
        log.error("worker task %s exited unexpectedly (exit code %s)", getattr(fn, "__name__", fn), proc.exitcode)
    raise AppError(500, "PROCESSING_FAILED", "The file could not be processed. Please try again or check the file.")
