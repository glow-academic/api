"""Attempt chat complete — marks a chat as completed.

Model calls this explicitly when it determines the chat is done.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.attempt.refresh import refresh_attempt_impl
from app.tools.entries.attempt_chat_completion.create import (
    create_attempt_chat_completion,
)


async def chat_complete_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    chat_id: UUID | None = None,
    message: str = "",
    **kwargs: Any,
):
    """Mark an attempt chat as completed."""
    if chat_id is None and "chat_id" in kwargs:
        chat_id = UUID(kwargs["chat_id"])
    if isinstance(chat_id, str):
        chat_id = UUID(chat_id)

    if not chat_id:
        raise ValueError("chat_id is required")

    async with pool.acquire() as conn:
        result = await create_attempt_chat_completion(
            conn,
            redis, chat_id=chat_id,
            session_id=session_id,
            message=message,
        )

    await refresh_attempt_impl(
        pool, redis, profile_id=profile_id, session_id=session_id,
        targets=["attempt_chat_completion_mv", "attempt_chat_mv"],
    )

    return {"completion_id": str(result.id), "chat_id": str(chat_id)}
