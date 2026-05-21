"""Attempt complete — marks an entire attempt as completed.

Idempotent primitive: creates attempt_completion_entry if not already present.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt.refresh import refresh_attempt
from app.tools.entries.attempt_completion.create import create_attempt_completion
from app.tools.entries.attempt_completion.refresh import refresh_attempt_completion


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

    async with pool.acquire() as conn:
        await refresh_attempt_completion(conn)
        await refresh_attempt(conn)

    return {"completion_id": str(result.id), "attempt_id": str(attempt_id)}
