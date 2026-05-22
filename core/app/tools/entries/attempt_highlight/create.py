"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_highlight.types import (
    CreateAttemptHighlightResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_highlight(
    conn: asyncpg.Connection,
    redis: Redis,
    strength_id: UUID,
    session_id: UUID,
    section: str,
    id: UUID | None = None,
    idx: int = 0,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptHighlightResponse:
    """Create an attempt_highlight entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_highlight_entry (id, strength_id, session_id, section, idx, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true)
        RETURNING id, created_at
        """,
        strength_id,
        session_id,
        section,
        idx,
        not soft,
        mcp,
        id,
    )
    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "highlight_id": str(entry_id),
        "strength_id": str(strength_id),
        "section": section,
        "idx": idx,
        "created_at": created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "attempt_highlight",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAttemptHighlightResponse(id=entry_id)
