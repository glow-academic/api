"""Canonical shared activity resolve operation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.activity.types import ResolveProblemApiResponse
from app.infra.group.resolve import resolve_group_impl
from app.tools.entries.calls.create import create_call
from app.tools.entries.resolves.create import create_resolve
from app.tools.entries.runs.create import create_run
from app.utils.cache.invalidate_tags import invalidate_tags

RESOLVE_TAGS = ["problems", "views", "activity", "summary"]


async def resolve_activity_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    problem_id: UUID,
    resolved: bool = True,
) -> ResolveProblemApiResponse:
    """Resolve or unresolve a problem entry.

    Flow:
      1. Create group -> run -> call -> resolve chain
      2. Invalidate cache tags
      3. Return response
    """
    # -- Create entry chain ---------------------------------------------------

    group_result = await resolve_group_impl(
        pool, redis,
        artifact_type="activity",
        profile_id=profile_id,
        session_id=session_id,
        include_history=False,
    )

    async with pool.acquire() as conn:
        run_result = await create_run(
            conn, redis, group_id=group_result.group_id, session_id=session_id
        )
        call_result = await create_call(
            conn, redis, run_id=run_result.id, session_id=session_id
        )
        await create_resolve(
            conn,
            redis, problem_id=problem_id,
            resolved=resolved,
            call_id=call_result.id,
        )

    # -- Invalidate cache -----------------------------------------------------

    await invalidate_tags(RESOLVE_TAGS, redis=redis)

    return ResolveProblemApiResponse(
        problem_id=problem_id,
        resolved=resolved,
        updated_at=datetime.now(),
    )
