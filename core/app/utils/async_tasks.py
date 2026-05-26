"""Background-task helper — fire-and-forget with strong refs + error logging.

asyncio garbage-collects tasks whose only reference is a local variable that
falls out of scope (including, classically, ``asyncio.create_task(...)`` with
no further reference). The canonical fix is to hold a strong reference in a
module-level set and discard on completion.

We use this for post-response audit persistence (msg/junction INSERTs that
the caller doesn't need to wait on) and any other "happens after the user
got their answer" work that shouldn't be on the response critical path.

Failures are logged but never re-raise — callers receive their successful
response regardless.

Usage:

    from app.utils.async_tasks import schedule_background

    schedule_background(_persist_audit_writes(...), label="audit_persist")
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# Strong refs so asyncio doesn't GC mid-flight.
_PENDING: set[asyncio.Task] = set()


def schedule_background(coro: Coroutine[Any, Any, Any], *, label: str) -> asyncio.Task:
    """Schedule ``coro`` as a fire-and-forget task.

    Returns the task (useful for tests that want to await completion). In
    production code, ignore the return — the caller is not expected to
    wait. Errors inside the task get logged with ``label`` for grep-ability;
    they never re-raise to the caller.
    """
    task = asyncio.create_task(coro)
    _PENDING.add(task)

    def _done(t: asyncio.Task) -> None:
        _PENDING.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.exception(
                f"async task '{label}' failed", extra={"error": str(exc)},
            )

    task.add_done_callback(_done)
    return task


async def wait_for_pending(timeout: float = 5.0) -> None:
    """Await all currently-pending background tasks.

    Useful in tests and graceful-shutdown paths. Returns when all tasks
    complete or the timeout elapses. Does NOT cancel — just observes.
    """
    if not _PENDING:
        return
    pending = list(_PENDING)
    try:
        await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"wait_for_pending: timed out with {len(_PENDING)} task(s) still running")
