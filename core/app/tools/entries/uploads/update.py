"""Uploads UPDATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore


async def set_upload_size(
    conn: asyncpg.Connection,
    upload_id: UUID,
    size: int,
) -> bool:
    """Update an ``uploads_entry.size``. Used after streamed / reserved
    writes land in a previously empty upload so the row reflects reality.

    Returns ``True`` if a row was updated, ``False`` if the upload_id was
    not found.
    """
    result = await conn.execute(
        """
        UPDATE uploads_entry
           SET size = $1
         WHERE id = $2
        """,
        size,
        upload_id,
    )
    return result.endswith(" 1")
