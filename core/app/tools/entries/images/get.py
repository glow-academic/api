"""Images GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.images.types import GetImageResponse


async def get_image(
    conn: asyncpg.Connection,
    image_id: UUID,
) -> GetImageResponse | None:
    """Get an images entry by ID."""
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
