"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_hint.types import CreateAttemptHintResponse
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_hint(
    conn: asyncpg.Connection,
    redis: Redis,
    message_id: UUID,
    session_id: UUID,
    hint: str,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptHintResponse:
    """Create an attempt_hint entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_hint_entry
            (id, message_id, session_id, hint, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at
        """,
        message_id,
        session_id,
        hint,
        not soft,
        mcp,
        id,
    )
    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "hint_id": str(entry_id),
        "message_id": str(message_id),
        "hint": hint,
        "created_at": created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "attempt_hint",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAttemptHintResponse(id=entry_id)
