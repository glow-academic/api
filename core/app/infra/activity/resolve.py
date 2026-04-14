"""Canonical shared activity resolve operation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.activity.types import ResolveProblemApiResponse
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
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

    async with pool.acquire() as conn:
        group_result = await create_group(conn, session_id=session_id, artifact_type="activity")  # TODO: fix logic
        run_result = await create_run(
            conn, group_id=group_result.id, session_id=session_id
        )
        call_result = await create_call(
            conn, run_id=run_result.id, session_id=session_id
        )
        await create_resolve(
            conn,
            problem_id=problem_id,
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
