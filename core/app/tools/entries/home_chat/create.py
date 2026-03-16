"""Home chat CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.home_chat.types import CreateHomeChatResponse


async def create_home_chat(
    conn: asyncpg.Connection,
    home_id: UUID,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateHomeChatResponse:
    """Create a home_chat_entry bridge row."""
    row_id = await conn.fetchval(
        """
        INSERT INTO home_chat_entry (id, home_id, chat_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        home_id,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row_id is None:
        raise ValueError("Failed to create home_chat_entry")

    return CreateHomeChatResponse(id=row_id)
