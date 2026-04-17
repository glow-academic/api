"""Agent problem logic — per-artifact diagnostic entry point."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.agent.refresh import refresh_agent_impl
from app.infra.agent.types import ProblemAgentApiResponse
from app.tools.entries.problems.create import create_problem as create_problem_entry

ARTIFACT_TYPE = "agent"
VALID_PROBLEM_TYPES = ("feature", "bug", "question", "other")


async def problem_agent_impl(
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
) -> ProblemAgentApiResponse:
    """Create a problem entry for the agent artifact."""
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

    identity = await resolve_profile_identity_context(pool, profile_id, redis)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if not has_permission(identity.role_permissions, ARTIFACT_TYPE, "problem"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to report agent problems.",
        )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return ProblemAgentApiResponse(
                problem_id=idempotency_key,
                success=True,
                message="Problem rejected",
                idempotency_key=idempotency_key,
            )
        soft = False

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

    await refresh_agent_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or problem_result.id,
    )

    return ProblemAgentApiResponse(
        problem_id=problem_result.id,
        success=True,
        message=(
            "Problem accepted"
            if accept is not None and idempotency_key is not None
            else "Problem created (pending acceptance)"
            if soft
            else "Problem created successfully"
        ),
        idempotency_key=idempotency_key or problem_result.id,
    )
