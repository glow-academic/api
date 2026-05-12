"""Attempt message CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_message.types import (
    CreateAttemptMessageResponse,
)


async def create_attempt_message(
    conn: asyncpg.Connection,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptMessageResponse:
    """Create an attempt_message_entry row. Text-only — audio attaches
    are separate entries created via ``create_attempt_audio``.
    """
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_message_entry (id, chat_id, session_id, active, mcp, generated, created_at)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true, COALESCE($6, NOW()))
        RETURNING id
        """,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    if entry_id is None:
        raise ValueError("Failed to create attempt_message entry")

    return CreateAttemptMessageResponse(id=entry_id)
