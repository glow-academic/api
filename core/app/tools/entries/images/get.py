"""Images GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.images.types import GetImageResponse
from app.utils.cache.hedged_row import read_back_row


async def get_image(
    conn: asyncpg.Connection,
    image_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetImageResponse | None:
    """Get an images entry by ID."""
    if not bypass_cache:
        cached = await read_back_row(redis, "images", image_id)
        if cached is not None:
            return GetImageResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, session_id, active, mcp, generated
        FROM images_entry
        WHERE id = $1
    """,
        image_id,
    )

    if row is None:
        return None

    return GetImageResponse(
        id=row["id"],
        session_id=row["session_id"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
