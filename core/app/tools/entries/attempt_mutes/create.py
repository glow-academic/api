"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_mutes.types import (
    CreateAttemptMutesResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_mutes(
    conn: asyncpg.Connection,
    redis: Redis,
    conversation_id: UUID,
    session_id: UUID,
    muted: bool,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptMutesResponse:
    """Create an attempt_mutes entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_mutes_entry (id, conversation_id, session_id, muted, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at
        """,
        conversation_id,
        session_id,
        muted,
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
        "conversation_id": str(conversation_id),
        "muted": muted,
        "session_id": str(session_id) if session_id is not None else None,
    }
    await write_back_row(
        redis,
        "attempt_mutes",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAttemptMutesResponse(id=entry_id)
