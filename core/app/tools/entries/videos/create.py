"""Videos CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.videos.types import CreateVideoResponse
from app.utils.cache.hedged_row import write_back_row


async def create_video(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    *,
    id: UUID | None = None,
    length_seconds: int = 0,
    videos_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateVideoResponse:
    """Create a videos entry with optional link to videos resource."""
    row = await conn.fetchrow(
        """
        INSERT INTO videos_entry (id, session_id, length_seconds, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true)
        RETURNING id, created_at
    """,
        session_id,
        length_seconds,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create videos entry")

    video_id = row["id"]
    actual_created_at = row["created_at"]

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

    # Cache-row-superset: GET (entry columns) + SEARCH (videos_mv = videos_entry
    # JOIN videos_resource) shape fields. Upload-denorm fields are None until
    # the corresponding video_uploads row links in.
    fresh_row = {
        "id": str(video_id),
        "video_id": str(video_id),
        "session_id": str(session_id),
        "length_seconds": length_seconds,
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "created_at": actual_created_at.isoformat(),
        "videos_id": str(videos_id) if videos_id else None,
        "upload_id": None,
        "file_path": None,
        "mime_type": None,
        "size": None,
    }
    await write_back_row(
        redis,
        "videos",
        video_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateVideoResponse(id=video_id)
