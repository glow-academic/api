"""Cohort problem logic — composable infra architecture.

Creates a problem entry scoped to the cohort artifact type.
The group -> run -> call chain is handled by the route's audit wrapper.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.cohort.types import ProblemCohortApiResponse
from app.infra.cohort.refresh import refresh_cohort_impl
from app.tools.entries.problems.create import create_problem as create_problem_entry

ARTIFACT_TYPE = "cohort"
VALID_PROBLEM_TYPES = ("feature", "bug", "question", "other")


async def problem_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    type: str,
    message: str,
    call_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> ProblemCohortApiResponse:
    """Create a problem entry for the cohort artifact.

    Lifecycle via soft + accept:
      - soft=True: create problem with active=false
      - accept=True: promote (set active=true)
      - accept=False: no-op
    """
    # -- Short-circuit: ack path ------------------------------------------------
    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                await create_problem_entry(
                    conn,
                    session_id=session_id,
                    call_id=call_id or UUID(int=0),
                    type=type,
                    artifact_type=ARTIFACT_TYPE,
                    message=message,
                    id=idempotency_key,
                    soft=False,
                )
        return ProblemCohortApiResponse(
            problem_id=idempotency_key,
            success=True,
            message="Problem accepted" if accept else "Problem rejected",
            idempotency_key=idempotency_key,
        )

    # -- Step 1: Validation -----------------------------------------------------

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

    # -- Step 2: Profile context ------------------------------------------------

    identity = await resolve_profile_identity_context(pool, profile_id, redis)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 3: Permission check -----------------------------------------------

    if not has_permission(identity.role_permissions, ARTIFACT_TYPE, "problem"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to report cohort problems.",
        )

    # -- Step 4: Create problem entry -------------------------------------------

    async with pool.acquire() as conn:
        problem_result = await create_problem_entry(
            conn,
            session_id=session_id,
            call_id=call_id or UUID(int=0),
            type=type,
            artifact_type=ARTIFACT_TYPE,
            message=message,
            id=idempotency_key,
            profile_id=identity.profiles_id,
            soft=soft,
        )

    # -- Step 5: Refresh + invalidate ------------------------------------------

    await refresh_cohort_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or problem_result.id,
    )

    return ProblemCohortApiResponse(
        problem_id=problem_result.id,
        success=True,
        message="Problem created (pending acceptance)" if soft else "Problem created successfully",
        idempotency_key=idempotency_key,
    )
