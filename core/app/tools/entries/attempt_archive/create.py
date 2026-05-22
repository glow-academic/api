"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_archive.types import (
    CreateAttemptArchiveResponse,
)
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_attempt_archive(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_id: UUID,
    session_id: UUID,
    archived: bool,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptArchiveResponse:
    """Create an attempt_archive entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_archive_entry (id, attempt_id, session_id, archived, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at
        """,
        attempt_id,
        session_id,
        archived,
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
        "attempt_id": str(attempt_id),
        "archived": archived,
        "session_id": str(session_id) if session_id is not None else None,
    }
    await write_back_row(
        redis,
        "attempt_archive",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )
    # Parent attempt's MV ``is_archived`` flag flips.
    await invalidate_row(redis, "attempt", attempt_id)

    return CreateAttemptArchiveResponse(id=entry_id)
