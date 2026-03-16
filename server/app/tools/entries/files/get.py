"""Files GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.files.types import GetFileResponse


async def get_file(
    conn: asyncpg.Connection,
    file_id: UUID,
) -> GetFileResponse | None:
    """Get a files entry by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, session_id, active, mcp, generated
        FROM files_entry
        WHERE id = $1
    """,
        file_id,
    )

    if row is None:
        return None

    return GetFileResponse(
        id=row["id"],
        session_id=row["session_id"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
