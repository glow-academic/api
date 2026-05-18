"""Videos CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.videos.types import CreateVideoResponse


async def create_video(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    id: UUID | None = None,
    length_seconds: int = 0,
    videos_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateVideoResponse:
    """Create a videos entry with optional link to videos resource."""
    video_id = await conn.fetchval(
        """
        INSERT INTO videos_entry (id, session_id, length_seconds, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true)
        RETURNING id
    """,
        session_id,
        length_seconds,
        not soft,
        mcp,
        id,
    )

    if video_id is None:
        raise ValueError("Failed to create videos entry")

    if videos_id is not None:
        await conn.execute(
            """
            INSERT INTO videos_videos_connection (video_id, videos_id, mcp)
            VALUES ($1, $2, $3)
        """,
            video_id,
            videos_id,
            mcp,
        )

    return CreateVideoResponse(id=video_id)
