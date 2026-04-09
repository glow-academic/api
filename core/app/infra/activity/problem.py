"""Canonical shared activity problem operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activity.types import CreateProblemApiResponse
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import create_problem as create_problem_entry
from app.tools.entries.runs.create import create_run
from app.utils.cache.invalidate_tags import invalidate_tags

PROBLEM_TAGS = ["problems", "views", "activity"]

VALID_PROBLEM_TYPES = ("feature", "bug", "question", "other")


async def problem_activity_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    type: str,
    message: str,
) -> CreateProblemApiResponse:
    """Create a new problem entry.

    Flow:
      1. Validate type and message
      2. Resolve profile identity context
      3. Create group -> run -> call -> problem chain
      4. Invalidate cache tags
      5. Return response
    """
    # -- Validation -----------------------------------------------------------

    if type not in VALID_PROBLEM_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid problem type: {type}",
        )

    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="Message is required")

    if len(message) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Message must be less than 1000 characters",
        )

    # -- Profile context ------------------------------------------------------

    identity = await resolve_profile_identity_context(pool, profile_id, redis)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Create entry chain ---------------------------------------------------

    async with pool.acquire() as conn:
        group_result = await create_group(conn, session_id=session_id)
        run_result = await create_run(
            conn, group_id=group_result.id, session_id=session_id
        )
        call_result = await create_call(
            conn, run_id=run_result.id, session_id=session_id
        )
        problem_result = await create_problem_entry(
            conn,
            session_id=session_id,
            call_id=call_result.id,
            type=type,
            message=message,
            profile_id=identity.profiles_id,
        )

    # -- Invalidate cache -----------------------------------------------------

    await invalidate_tags(PROBLEM_TAGS, redis=redis)

    return CreateProblemApiResponse(
        problem_id=problem_result.id,
        success=True,
        message="Problem created successfully",
    )
