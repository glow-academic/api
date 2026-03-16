"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_archive.types import (
    CreateTestArchiveResponse,
)


async def create_test_archive(
    conn: asyncpg.Connection,
    test_id: UUID,
    call_id: UUID,
    archived: bool,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestArchiveResponse:
    """Create a test_archive entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO test_archive_entry (id, test_id, call_id, archived, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        test_id,
        call_id,
        archived,
        not soft,
        mcp,
        id,
    )
    return CreateTestArchiveResponse(id=entry_id)
