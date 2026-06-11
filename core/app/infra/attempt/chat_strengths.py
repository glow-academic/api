"""Attempt chat strengths — thin infra impl for generate pipeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.attempt.permissions import enforce_attempt_access_by_grade
from app.infra.attempt.refresh import refresh_attempt_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.attempt_strength.create import create_attempt_strength


async def chat_strengths_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    grade_id: UUID | None = None,
    message_id: UUID | None = None,
    name: str = "",
    description: str = "",
    **kwargs: Any,
):
    """Create a strength entry for a grade."""
    if grade_id is None and "grade_id" in kwargs:
        grade_id = UUID(kwargs["grade_id"])
    if message_id is None and "message_id" in kwargs:
        message_id = UUID(kwargs["message_id"])
    if isinstance(grade_id, str):
        grade_id = UUID(grade_id)
    if isinstance(message_id, str):
        message_id = UUID(message_id)
    if not name and "name" in kwargs:
        name = str(kwargs["name"])
    if not description and "description" in kwargs:
        description = str(kwargs["description"])

    if not grade_id:
        raise ValueError("grade_id is required")
    if not message_id:
        raise ValueError("message_id is required")

    # Authorization (was MISSING — any authenticated profile could annotate ANY
    # student's graded attempt). Mirror the chat_grade gate via the shared
    # attempt-mutation path: resolve grade → chat → owner and enforce
    # self/super-admin/strictly-higher-role-in-department. Resolved outside the
    # write transaction so nested pool acquires can't starve a small pool.
    requester = await resolve_profile_identity_context(pool, profile_id, redis)
    await enforce_attempt_access_by_grade(pool, redis, grade_id=grade_id, requester=requester)

    with timed("db_write"):
        async with pool.acquire() as conn:
            result = await create_attempt_strength(
                conn,
                redis, grade_id=grade_id,
                message_id=message_id,
                session_id=session_id,
                name=name or "Untitled strength",
                description=description or "No description provided",
            )

    with timed("refresh"):
        await refresh_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["attempt_strength_mv"],
        )

    return {"strength_id": str(result.id)}
