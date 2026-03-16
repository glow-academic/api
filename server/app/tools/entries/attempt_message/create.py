"""Attempt message CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_message.types import (
    CreateAttemptMessageResponse,
)


async def create_attempt_message(
    conn: asyncpg.Connection,
    chat_id: UUID,
    message_id: UUID,
    call_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptMessageResponse:
    """Create an attempt_message_entry row."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_message_entry (id, chat_id, call_id, active, mcp, generated)
        VALUES (COALESCE($6::uuid, $1::uuid), $2, $3, $4, $5, true)
        RETURNING id
        """,
        message_id,
        chat_id,
        call_id,
        not soft,
        mcp,
        id,
    )

    if entry_id is None:
        raise ValueError("Failed to create attempt_message entry")

    return CreateAttemptMessageResponse(id=entry_id)
