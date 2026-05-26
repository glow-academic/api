"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_replacement.types import (
    CreateAttemptReplacementResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_replacement(
    conn: asyncpg.Connection,
    redis: Redis,
    improvement_id: UUID,
    session_id: UUID,
    section: str,
    replace: str,
    id: UUID | None = None,
    idx: int = 0,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptReplacementResponse:
    """Create an attempt_replacement entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_replacement_entry (id, improvement_id, session_id, section, "replace", idx, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at
        """,
        improvement_id,
        session_id,
        section,
        replace,
        idx,
        not soft,
        mcp,
        id,
    )
    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "replacement_id": str(entry_id),
        "improvement_id": str(improvement_id),
        "section": section,
        "replace_text": replace,
        "idx": idx,
        "created_at": created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "attempt_replacement",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAttemptReplacementResponse(id=entry_id)
