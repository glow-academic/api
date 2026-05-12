"""Run a generation either synchronously (blocking) or in the background.

Used by every ``generate_<art>_impl`` so all 20 share the same
blocking-vs-fire-and-forget logic, the same background failure path,
and the same ``<artifact>.generate.failed`` emit on background errors.

POC default at every caller: ``wait_for_complete=True`` (blocking).
Pass ``False`` to return immediately with ``prepared.run_id`` and let
the actual ``execute_generation`` + per-artifact refresh finish in the
background.

Failure semantics:
- Blocking (``wait_for_complete=True``): exceptions log + emit
  ``<artifact>.generate.failed`` to the hub AND re-raise so the HTTP
  route surfaces a 5xx (preserves existing behavior).
- Background (``wait_for_complete=False``): same log + hub emit, but
  the exception is swallowed by the task so it can't crash the request
  that already returned. SSE consumers are the failure channel.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.generation.execute import ExecuteGenerationResult, execute_generation
from app.infra.generation.prepare import PrepareGenerationResult

logger = logging.getLogger(__name__)


RefreshFn = Callable[..., Awaitable[Any]]


async def run_generation_with_refresh(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    prepared: PrepareGenerationResult,
    sid: str,
    tool_soft: bool,
    artifact_type: str,
    refresh_fn: RefreshFn | None,
    profile_id: UUID,
    session_id: UUID,
    group_id: UUID | str,
    internal_sio: Any,
    wait_for_complete: bool = True,
    operation_key: UUID | None = None,
    refresh_session_id: bool = True,
) -> ExecuteGenerationResult | None:
    """Execute the prepared generation and then refresh the artifact MVs.

    When ``wait_for_complete=True`` (default), this awaits both steps
    in-band, re-raises any exception, and returns the
    ``ExecuteGenerationResult`` so the caller can read
    ``produced_media`` and bubble it onto the API response.

    When ``False``, it spawns an ``asyncio.create_task`` and returns
    ``None`` immediately; the caller can rely on ``prepared.run_id``
    being valid for a paired ``X_Watch``.
    """

    async def _run() -> ExecuteGenerationResult | None:
        try:
            result = await execute_generation(
                pool, redis,
                prepared=prepared,
                sid=sid,
                tool_soft=tool_soft,
            )
            if refresh_fn is not None:
                refresh_kwargs: dict[str, Any] = {"profile_id": profile_id}
                if refresh_session_id:
                    refresh_kwargs["session_id"] = session_id
                if operation_key is not None:
                    refresh_kwargs["operation_key"] = operation_key
                await refresh_fn(pool, redis, **refresh_kwargs)
            return result
        except Exception as exc:
            logger.exception(
                "%s generation failed for run_id=%s",
                artifact_type, prepared.run_id,
            )
            try:
                await internal_sio.emit(
                    f"{artifact_type}.generate.failed",
                    {
                        "artifact_type": artifact_type,
                        "run_id": str(prepared.run_id),
                        "group_id": str(group_id),
                        "success": False,
                        "message": str(exc)[:500],
                    },
                )
            except Exception:
                logger.exception(
                    "failed to emit %s.generate.failed for run_id=%s",
                    artifact_type, prepared.run_id,
                )
            if wait_for_complete:
                raise
            return None

    if wait_for_complete:
        return await _run()

    task = asyncio.create_task(_run())
    task.add_done_callback(_log_background_completion)
    return None


def _log_background_completion(task: "asyncio.Task[ExecuteGenerationResult | None]") -> None:
    """asyncio gives `task.exception()` retrieval ability that suppresses
    the 'Task exception was never retrieved' warning. ``_run`` already
    logged + hub-emitted; this just acknowledges retrieval."""
    if task.cancelled():
        logger.warning("background generation task was cancelled")
        return
    exc = task.exception()
    if exc is not None:
        logger.debug("background generation task ended with exception: %r", exc)
