"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_conversations.types import (
    CreateAttemptConversationsResponse,
)


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
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_conversations_entry (id, chat_id, session_id, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true)
        RETURNING id
        """,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
    )
    return CreateAttemptConversationsResponse(id=entry_id)
