"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_archive.types import (
    CreateTestArchiveResponse,
)
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_test_archive(
    conn: asyncpg.Connection,
    redis: Redis,
    test_id: UUID,
    call_id: UUID,
    archived: bool,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestArchiveResponse:
    """Create a test_archive entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO test_archive_entry (id, test_id, call_id, archived, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at
        """,
        test_id,
        call_id,
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
        "test_id": str(test_id),
        "archived": archived,
        "call_id": str(call_id),
    }
    await write_back_row(
        redis,
        "test_archive",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )
    # Bust the parent test write-back row: the MV derives ``archived`` from the
    # latest test_archive. The parent's cached row was written archived=False at
    # create-time; without this a cached parent GET shadows the hydrated MV with
    # stale archived state until TTL (#98 sibling). Mirrors attempt_archive.
    await invalidate_row(redis, "test", test_id)

    return CreateTestArchiveResponse(id=entry_id)
