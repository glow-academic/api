"""Home chat CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.home_chat.types import CreateHomeChatResponse
from app.utils.cache.hedged_row import write_back_row


async def create_home_chat(
    conn: asyncpg.Connection,
    redis: Redis,
    home_id: UUID,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateHomeChatResponse:
    """Create a home_chat_entry bridge row."""
    row = await conn.fetchrow(
        """
        INSERT INTO home_chat_entry (id, home_id, chat_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at, active, mcp
        """,
        home_id,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create home_chat_entry")
    row_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(row_id),
        "home_id": str(home_id),
        "chat_id": str(chat_id),
        "created_at": created_at.isoformat(),
        "active": row["active"],
        "generated": True,
        "mcp": row["mcp"],
        "session_id": str(session_id),
    }
    await write_back_row(
        redis,
        "home_chat",
        row_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateHomeChatResponse(id=row_id)
