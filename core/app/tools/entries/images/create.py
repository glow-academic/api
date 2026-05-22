"""Images CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.images.types import CreateImageResponse
from app.utils.cache.hedged_row import write_back_row


async def create_image(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    id: UUID | None = None,
    images_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateImageResponse:
    """Create an images entry with optional link to images resource."""
    row = await conn.fetchrow(
        """
        INSERT INTO images_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id, created_at
    """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create images entry")

    image_id = row["id"]
    actual_created_at = row["created_at"]

    if images_id is not None:
        await conn.execute(
            """
            INSERT INTO images_images_connection (image_id, images_id, mcp)
            VALUES ($1, $2, $3)
        """,
            image_id,
            images_id,
            mcp,
        )

    # Cache-row-superset: GET (entry columns) + SEARCH (images_mv = images_entry
    # JOIN images_resource) shape fields. Upload-denorm + quality_id are None
    # until corresponding image_uploads / quality link rows write in.
    fresh_row = {
        "id": str(image_id),
        "image_id": str(image_id),
        "session_id": str(session_id),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "created_at": actual_created_at.isoformat(),
        "images_id": str(images_id) if images_id else None,
        "upload_id": None,
        "file_path": None,
        "mime_type": None,
        "size": None,
        "quality_id": None,
    }
    await write_back_row(
        redis,
        "images",
        image_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateImageResponse(id=image_id)
