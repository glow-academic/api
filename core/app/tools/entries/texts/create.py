"""Texts CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.texts.types import CreateTextResponse
from app.utils.cache.hedged_row import write_back_row


async def create_text(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    *,
    texts_id: UUID | None = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTextResponse:
    """Create a texts entry and optionally link it to a texts resource."""
    row = await conn.fetchrow(
        """
        INSERT INTO texts_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id, created_at
    """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create texts entry")

    text_id = row["id"]
    actual_created_at = row["created_at"]

    if texts_id is not None:
        await conn.execute(
            """
            INSERT INTO texts_texts_connection (texts_id, text_id)
            VALUES ($1, $2)
            """,
            texts_id,
            text_id,
        )

    # Cache-row-superset: GET (entry columns) + SEARCH (texts_mv = texts_entry
    # JOIN texts_resource) shape fields. Upload-denorm fields are None until
    # the corresponding text_uploads row links in.
    fresh_row = {
        "id": str(text_id),
        "text_id": str(text_id),
        "session_id": str(session_id),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "created_at": actual_created_at.isoformat(),
        "texts_id": str(texts_id) if texts_id else None,
        "upload_id": None,
        "file_path": None,
        "mime_type": None,
    }
    await write_back_row(
        redis,
        "texts",
        text_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateTextResponse(id=text_id)
