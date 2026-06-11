"""Attempt chat hints — thin infra impl for generate pipeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.attempt.permissions import enforce_attempt_access_by_message
from app.infra.attempt.refresh import refresh_attempt_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.attempt_hint.create import create_attempt_hint


async def chat_hints_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    message_id: UUID | None = None,
    hint: str = "",
    **kwargs: Any,
):
    """Create a hint entry for a message."""
    if message_id is None and "message_id" in kwargs:
        message_id = UUID(kwargs["message_id"])
    if isinstance(message_id, str):
        message_id = UUID(message_id)
    if not hint and "hint" in kwargs:
        hint = str(kwargs["hint"])

    if not message_id:
        raise ValueError("message_id is required")

    # Authorization (was MISSING — see chat_strengths). Resolve message → chat →
    # owner and enforce the shared attempt-mutation gate.
    requester = await resolve_profile_identity_context(pool, profile_id, redis)
    await enforce_attempt_access_by_message(pool, redis, message_id=message_id, requester=requester)

    with timed("db_write"):
        async with pool.acquire() as conn:
            result = await create_attempt_hint(
                conn,
                redis, message_id=message_id,
                session_id=session_id,
                hint=hint or "No hint provided",
            )

    with timed("refresh"):
        await refresh_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["attempt_hint_mv"],
        )

    return {"hint_id": str(result.id)}
