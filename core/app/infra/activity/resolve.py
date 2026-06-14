"""Canonical shared activity resolve operation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activity.types import ResolveProblemApiResponse
from app.infra.group.resolve import resolve_group_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.calls.create import create_call
from app.tools.entries.resolves.create import create_resolve
from app.tools.entries.runs.create import create_run
from app.utils.cache.invalidate_tags import invalidate_tags

RESOLVE_TAGS = ["problems", "views", "activity", "summary"]

# G1: admins + super-admin (role_level 0 = Super Administrator, 1 =
# Administrator) own the cross-user triage queue, so they may resolve any
# user's problem. Everyone else (instructional/guest/member) may resolve only
# their own report. Mirrors the level-numbering used across the identity layer.
_ADMIN_ROLE_LEVEL = 1


async def _enforce_problem_owner(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    problem_id: UUID,
) -> None:
    """G1: fail-closed cross-user ownership guard for problem resolve/unresolve.

    Problems are owner-scoped via ``profiles_problems_connection``. The HTTP
    ``POST /system/resolve`` and WS ``system.activity_resolve`` surfaces both
    take a caller-supplied ``problem_id`` and write the resolve with no
    ownership check, so any authenticated user could resolve/unresolve any
    other user's report and corrupt the admin triage queue. This resolves the
    problem's owning ``profiles_id`` and enforces it against the requester,
    with an admin/super-admin override (they manage the queue).

    Raises:
        HTTPException 403 if a non-admin requester does not own ``problem_id``.
    """
    requester = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if requester is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if requester.role_level <= _ADMIN_ROLE_LEVEL:
        # Admin / super-admin manage the cross-user triage queue.
        return

    async with pool.acquire() as conn:
        owner_profiles_id = await conn.fetchval(
            """
            SELECT profiles_id
            FROM profiles_problems_connection
            WHERE problem_id = $1
            LIMIT 1
            """,
            problem_id,
        )

    if owner_profiles_id is not None and owner_profiles_id == requester.profiles_id:
        return

    raise HTTPException(
        status_code=403,
        detail="You don't have permission to resolve this problem.",
    )


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
      1. Enforce cross-user ownership (G1)
      2. Create group -> run -> call -> resolve chain
      3. Invalidate cache tags
      4. Return response
    """
    # -- Ownership guard (G1) -------------------------------------------------

    await _enforce_problem_owner(
        pool, redis,
        profile_id=profile_id,
        session_id=session_id,
        problem_id=problem_id,
    )

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
