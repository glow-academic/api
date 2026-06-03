"""Parameter problem logic — per-artifact diagnostic entry point.

Creates a problem entry scoped to the parameter artifact type.
Follows the canonical persona/simulation problem flow:
  1. Validate type and message
  2. Resolve profile identity context
  3. Permission check — parameter:problem
  4. Ack short-circuit for dormant problem promotion/rejection
  5. Create problem entry
  6. Canonical parameter refresh
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.parameter.refresh import refresh_parameter_impl
from app.infra.parameter.types import ProblemParameterApiResponse
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.problems.create import create_problem as create_problem_entry

ARTIFACT_TYPE = "parameter"
VALID_PROBLEM_TYPES = ("feature", "bug", "question", "other")


async def problem_parameter_impl(
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
) -> ProblemParameterApiResponse:
    """Create a problem entry for the parameter artifact.

    Flow:
      1. Validate type and message
      2. Resolve profile identity context
      3. Permission check — parameter:problem
      4. Ack short-circuit for dormant problem promotion/rejection
      5. Create problem entry
      6. Canonical parameter refresh
    """
    # ── Step 1: Validation ─────────────────────────────────────────────

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

    # ── Step 2: Profile context ────────────────────────────────────────

    with timed("profile"):
        identity = await resolve_profile_identity_context(pool, profile_id, redis)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 3: Permission check ───────────────────────────────────────

    with timed("permissions"):
        if not has_permission(identity.role_permissions, ARTIFACT_TYPE, "problem"):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to report parameter problems.",
            )

    # ── Step 4: Ack short-circuit ──────────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                await create_problem_entry(
                    conn,
                    redis,
                    session_id=session_id,
                    call_id=call_id or UUID(int=0),
                    type=type,
                    artifact_type=ARTIFACT_TYPE,
                    message=message,
                    id=idempotency_key,
                    profile_id=identity.profiles_id,
                    soft=False,
                )
            await refresh_parameter_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key,
            )
        return ProblemParameterApiResponse(
            problem_id=idempotency_key,
            success=True,
            message="Problem accepted" if accept else "Problem rejected",
            idempotency_key=idempotency_key,
        )

    # ── Step 5: Create problem entry ───────────────────────────────────

    with timed("db_write"):
     async with pool.acquire() as conn:
        problem_result = await create_problem_entry(
            conn,
            redis,
            session_id=session_id,
            call_id=call_id or UUID(int=0),
            type=type,
            artifact_type=ARTIFACT_TYPE,
            message=message,
            id=idempotency_key,
            profile_id=identity.profiles_id,
            soft=soft,
        )

    # ── Step 6: Canonical refresh ──────────────────────────────────────

    with timed("refresh"):
        await refresh_parameter_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or problem_result.id,
        )

    return ProblemParameterApiResponse(
        problem_id=problem_result.id,
        success=True,
        message="Problem created (pending acceptance)" if soft else "Problem created successfully",
        idempotency_key=idempotency_key,
    )
