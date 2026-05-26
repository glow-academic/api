"""Image Uploads GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.image_uploads.types import GetImageUploadResponse
from app.utils.cache.hedged_row import read_back_row


async def get_image_upload(
    conn: asyncpg.Connection,
    image_upload_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetImageUploadResponse | None:
    """Get an image_uploads entry by ID."""
    if not bypass_cache:
        cached = await read_back_row(redis, "image_uploads", image_upload_id)
        if cached is not None:
            return GetImageUploadResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, image_id, upload_id, session_id,
               created_at, active, mcp, generated
        FROM image_uploads_entry
        WHERE id = $1
    """,
        image_upload_id,
    )

    if row is None:
        return None

    return GetImageUploadResponse(
        id=row["id"],
        image_id=row["image_id"],
        upload_id=row["upload_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
