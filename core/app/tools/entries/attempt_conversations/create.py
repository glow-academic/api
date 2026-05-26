"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_conversations.types import (
    CreateAttemptConversationsResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_conversations(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptConversationsResponse:
    """Create an attempt_conversations entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_conversations_entry (id, chat_id, session_id, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true)
        RETURNING id, created_at
        """,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
    )
    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp,
        "active": not soft,
        "chat_id": str(chat_id),
        "session_id": str(session_id) if session_id is not None else None,
    }
    await write_back_row(
        redis,
        "attempt_conversations",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAttemptConversationsResponse(id=entry_id)
