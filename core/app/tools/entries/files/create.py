"""Files CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.files.types import CreateFileResponse
from app.utils.cache.hedged_row import write_back_row


async def create_file(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    id: UUID | None = None,
    files_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateFileResponse:
    """Create a files entry with optional link to files resource."""
    row = await conn.fetchrow(
        """
        INSERT INTO files_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id, created_at
    """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create files entry")

    file_id = row["id"]
    actual_created_at = row["created_at"]

    if files_id is not None:
        await conn.execute(
            """
            INSERT INTO file_files_connection (file_id, files_id, mcp)
            VALUES ($1, $2, $3)
        """,
            file_id,
            files_id,
            mcp,
        )

    fresh_row = {
        "id": str(file_id),
        "session_id": str(session_id),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "created_at": actual_created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "files",
        file_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateFileResponse(id=file_id)
