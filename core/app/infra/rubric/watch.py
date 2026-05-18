"""Rubric watch — one-shot block-until-done for the tool layer.

The HTTP route ``GET /rubric/watch`` stays as live SSE for the browser.
This impl is its tool-layer sibling — same hub events, but returns a
single ``WatchApiResponse`` describing which runs finished and what
they produced.

Function name matches the ``{operation}_{artifact}_impl`` discovery
convention so ``(rubric, watch)`` auto-resolves to this callable
without needing an INFRA_OPS override.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra._watch import WatchApiResponse, watch_runs_impl


async def watch_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    group_id: UUID,
    run_id: UUID | None = None,
    wait_for_complete: bool = True,
    timeout_seconds: int = 120,
    **_kwargs,
) -> WatchApiResponse:
    """Watch a rubric-scoped run in ``group_id``."""
    return await watch_runs_impl(
        pool,
        redis,
        artifact_type="rubric",
        group_id=group_id,
        run_id=run_id,
        wait_for_complete=wait_for_complete,
        timeout_seconds=timeout_seconds,
        profile_id=profile_id,
        session_id=session_id,
    )
