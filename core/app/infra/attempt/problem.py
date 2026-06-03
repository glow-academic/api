"""Attempt problem logic — per-artifact diagnostic entry point.

Creates a problem entry scoped to the attempt artifact type.
Follows the same group → run → call → problem chain as activity/problem.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.attempt.types import ProblemAttemptApiResponse
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.problems.create import create_problem as create_problem_entry
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT_TYPE = "attempt"
PROBLEM_TAGS = ["problems", "views", "attempts"]
VALID_PROBLEM_TYPES = ("feature", "bug", "question", "other")


async def problem_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    type: str,
    message: str,
) -> ProblemAttemptApiResponse:
    """Create a problem entry for the attempt artifact."""
    if type not in VALID_PROBLEM_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid problem type: {type}")

    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="Message is required")

    if len(message) > 1000:
        raise HTTPException(status_code=400, detail="Message must be less than 1000 characters")

    with timed("profile"):
        identity = await resolve_profile_identity_context(pool, profile_id, redis)
    if identity is None:
        raise HTTPException(status_code=401, detail="Profile not found. Please sign in again.")

    if not has_permission(identity.role_permissions, ARTIFACT_TYPE, "problem"):
        raise HTTPException(status_code=403, detail="You don't have permission to report attempt problems.")

    with timed("db_write"):
     async with pool.acquire() as conn:
        problem_result = await create_problem_entry(
            conn,
            redis,
            session_id=session_id,
            call_id=UUID(int=0),
            type=type,
            artifact_type=ARTIFACT_TYPE,
            message=message,
            profile_id=identity.profiles_id,
        )

    await invalidate_tags(PROBLEM_TAGS, redis=redis)

    return ProblemAttemptApiResponse(
        problem_id=problem_result.id,
        success=True,
        message="Problem created successfully",
    )
