"""Attempt chat analyses — thin infra impl for generate pipeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.attempt.refresh import refresh_attempt_impl
from app.infra.server_timing import timed
from app.tools.entries.attempt_analysis.create import create_attempt_analysis


async def chat_analyses_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    grade_id: UUID | None = None,
    content: str = "",
    **kwargs: Any,
):
    """Create an analysis entry for a grade."""
    if grade_id is None and "grade_id" in kwargs:
        grade_id = UUID(kwargs["grade_id"])
    if isinstance(grade_id, str):
        grade_id = UUID(grade_id)
    if not content and "content" in kwargs:
        content = str(kwargs["content"])

    if not grade_id:
        raise ValueError("grade_id is required")

    with timed("db_write"):
        async with pool.acquire() as conn:
            result = await create_attempt_analysis(
                conn,
                redis, grade_id=grade_id,
                session_id=session_id,
                content=content or "No analysis provided",
            )

    with timed("refresh"):
        await refresh_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["attempt_analysis_mv"],
        )

    return {"analysis_id": str(result.id)}
