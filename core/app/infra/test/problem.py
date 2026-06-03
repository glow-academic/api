"""Test problem logic — per-artifact diagnostic entry point.

Creates a problem entry scoped to the test artifact type.
Follows the same group -> run -> call -> problem chain as activity/problem.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.group.resolve import resolve_group_impl
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.test.types import ProblemTestApiResponse
from app.tools.entries.calls.create import create_call
from app.tools.entries.problems.create import create_problem as create_problem_entry
from app.tools.entries.runs.create import create_run
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT_TYPE = "test"
PROBLEM_TAGS = ["problems", "views", "tests"]
VALID_PROBLEM_TYPES = ("feature", "bug", "question", "other")


async def problem_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    type: str,
    message: str,
) -> ProblemTestApiResponse:
    """Create a problem entry for the test artifact.

    Flow:
      1. Validate type and message
      2. Resolve profile identity context
      3. Permission check -- test:problem
      4. Create group -> run -> call -> problem chain
      5. Invalidate cache tags
    """
    # -- Step 1: Validation -------------------------------------------------

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

    # -- Step 2: Profile context --------------------------------------------

    with timed("profile"):
        identity = await resolve_profile_identity_context(pool, profile_id, redis)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 3: Permission check -------------------------------------------

    if not has_permission(identity.role_permissions, ARTIFACT_TYPE, "problem"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to report test problems.",
        )

    # -- Step 4: Create entry chain -----------------------------------------

    with timed("group"):
        group_result = await resolve_group_impl(
            pool, redis,
            artifact_type=ARTIFACT_TYPE,
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )

    with timed("db_write"):
     async with pool.acquire() as conn:
        run_result = await create_run(
            conn, redis, group_id=group_result.group_id, session_id=session_id
        )
        call_result = await create_call(
            conn, redis, run_id=run_result.id, session_id=session_id
        )
        problem_result = await create_problem_entry(
            conn,
            redis,
            session_id=session_id,
            call_id=call_result.id,
            type=type,
            artifact_type=ARTIFACT_TYPE,
            message=message,
            profile_id=identity.profiles_id,
        )

    # -- Step 5: Invalidate cache -------------------------------------------

    await invalidate_tags(PROBLEM_TAGS, redis=redis)

    return ProblemTestApiResponse(
        problem_id=problem_result.id,
        success=True,
        message="Problem created successfully",
    )
