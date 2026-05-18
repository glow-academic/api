"""Texts GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.texts.types import GetTextResponse


async def get_text(
    conn: asyncpg.Connection,
    text_id: UUID,
) -> GetTextResponse | None:
    """Get a texts entry by ID."""
    row = await conn.fetchrow(
        """
        SELECT id, session_id, active, mcp, generated
        FROM texts_entry
        WHERE id = $1
    """,
        text_id,
    )

    if row is None:
        return None

    return GetTextResponse(
        id=row["id"],
        session_id=row["session_id"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
