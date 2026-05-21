"""Attempt complete — marks an entire attempt as completed.

Idempotent primitive: creates attempt_completion_entry if not already present.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.attempt.refresh import refresh_attempt_impl
from app.tools.entries.attempt_completion.create import create_attempt_completion


async def complete_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    attempt_id: UUID | None = None,
    message: str = "",
    **kwargs: Any,
):
    """Mark an attempt as completed."""
    if attempt_id is None and "attempt_id" in kwargs:
        attempt_id = UUID(kwargs["attempt_id"])
    if isinstance(attempt_id, str):
        attempt_id = UUID(attempt_id)

    if not attempt_id:
        raise ValueError("attempt_id is required")

    async with pool.acquire() as conn:
        result = await create_attempt_completion(
            conn,
            redis, attempt_id=attempt_id,
            session_id=session_id,
            message=message,
        )

    await refresh_attempt_impl(
        pool, redis, profile_id=profile_id, session_id=session_id,
        targets=["attempt_completion_mv", "attempt_mv"],
    )

    return {"completion_id": str(result.id), "attempt_id": str(attempt_id)}
