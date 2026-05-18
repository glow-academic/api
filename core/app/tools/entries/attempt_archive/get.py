"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_archive.types import (
    GetAttemptArchiveResponse,
)

MV_NAME = "attempt_archive_mv"


async def get_attempt_archives(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetAttemptArchiveResponse]:
    """Get attempt_archive entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", ids)
    return [GetAttemptArchiveResponse(**dict(r)) for r in rows]
