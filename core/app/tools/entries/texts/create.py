"""Texts CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.texts.types import CreateTextResponse


async def create_text(
    conn: asyncpg.Connection,
    session_id: UUID,
    *,
    texts_id: UUID | None = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTextResponse:
    """Create a texts entry and optionally link it to a texts resource."""
    text_id = await conn.fetchval(
        """
        INSERT INTO texts_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id
    """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if text_id is None:
        raise ValueError("Failed to create texts entry")

    if texts_id is not None:
        await conn.execute(
            """
            INSERT INTO texts_texts_connection (texts_id, text_id)
            VALUES ($1, $2)
            """,
            texts_id,
            text_id,
        )

    return CreateTextResponse(id=text_id)
