"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_archive.types import (
    GetTestArchiveResponse,
)

MV_NAME = "test_archive_mv"


async def get_test_archives(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetTestArchiveResponse]:
    """Get test_archive entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", ids)
    return [GetTestArchiveResponse(**dict(r)) for r in rows]
