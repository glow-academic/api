"""Videos GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.videos.types import GetVideoResponse


async def get_video(
    conn: asyncpg.Connection,
    video_id: UUID,
) -> GetVideoResponse | None:
    """Get a videos entry by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, session_id, length_seconds, active, mcp, generated
        FROM videos_entry
        WHERE id = $1
    """,
        video_id,
    )

    if row is None:
        return None

    return GetVideoResponse(
        id=row["id"],
        session_id=row["session_id"],
        length_seconds=row["length_seconds"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
