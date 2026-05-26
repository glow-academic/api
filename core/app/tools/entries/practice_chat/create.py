"""Practice chat CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.practice_chat.types import CreatePracticeChatResponse
from app.utils.cache.hedged_row import write_back_row


async def create_practice_chat(
    conn: asyncpg.Connection,
    redis: Redis,
    practice_id: UUID,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreatePracticeChatResponse:
    """Create a practice_chat_entry bridge row."""
    row = await conn.fetchrow(
        """
        INSERT INTO practice_chat_entry (id, practice_id, chat_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at
        """,
        practice_id,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create practice_chat_entry")
    row_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(row_id),
        "practice_id": str(practice_id),
        "chat_id": str(chat_id),
        "created_at": actual_created_at.isoformat(),
        "active": not soft,
        "generated": True,
        "mcp": mcp,
        "session_id": str(session_id),
    }
    await write_back_row(
        redis,
        "practice_chat",
        row_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreatePracticeChatResponse(id=row_id)
