"""Images CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.images.types import CreateImageResponse


async def create_image(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    images_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateImageResponse:
    """Create an images entry with optional link to images resource."""
    image_id = await conn.fetchval(
        """
        INSERT INTO images_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id
    """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if image_id is None:
        raise ValueError("Failed to create images entry")

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

    return CreateImageResponse(id=image_id)
