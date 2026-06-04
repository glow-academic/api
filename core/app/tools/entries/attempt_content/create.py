"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_content.types import (
    CreateAttemptContentResponse,
)
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_attempt_content(
    conn: asyncpg.Connection,
    redis: Redis,
    message_id: UUID,
    session_id: UUID,
    content: str,
    persona_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptContentResponse:
    """Create an attempt_content entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_content_entry
            (id, message_id, session_id, content, persona_id, active, mcp, generated, created_at)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true, COALESCE($8, NOW()))
        RETURNING id, created_at
        """,
        message_id,
        session_id,
        content,
        persona_id,
        not soft,
        mcp,
        id,
        created_at,
    )
    if row is None:
        raise ValueError("Failed to create attempt_content entry")
    entry_id = row["id"]
    actual_created_at = row["created_at"]

    # ``idx`` is computed via row_number() OVER PARTITION BY message_id in
    # the MV — not knowable race-free at insert time. Cache row stores None;
    # readers tolerate it (types.py defaults idx to None). Search has no idx
    # filter, so cached rows merge into results cleanly.
    fresh_row = {
        "content_id": str(entry_id),
        "message_id": str(message_id),
        "content": content,
        "persona_entry_id": str(persona_id),
        "idx": None,
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
        "id": str(entry_id),
    }
    if actual_created_at is not None:
        await write_back_row(
            redis,
            "attempt_content",
            entry_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    # Parent attempt_message's cached row carries ``type``, derived in
    # attempt_message_mv from the message's first attempt_content_entry
    # (first_content.persona_id vs user_persona_id). Attaching this content
    # row to ``message_id`` changes that derived type, so the attempt_message
    # cache (keyed by message_id) is now stale — bust it so the next
    # get/search_attempt_messages reflects the type from the MV. Mirrors how
    # message_uploads/create invalidates "attempt_message".
    await invalidate_row(redis, "attempt_message", message_id)

    return CreateAttemptContentResponse(id=entry_id)
