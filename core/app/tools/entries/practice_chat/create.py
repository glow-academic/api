"""Practice chat CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.practice_chat.types import CreatePracticeChatResponse


async def create_practice_chat(
    conn: asyncpg.Connection,
    practice_id: UUID,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreatePracticeChatResponse:
    """Create a practice_chat_entry bridge row."""
    row_id = await conn.fetchval(
        """
        INSERT INTO practice_chat_entry (id, practice_id, chat_id, session_id, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        practice_id,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row_id is None:
        raise ValueError("Failed to create practice_chat_entry")

    return CreatePracticeChatResponse(id=row_id)
