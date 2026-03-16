"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_mutes.types import (
    CreateAttemptMutesResponse,
)


async def create_attempt_mutes(
    conn: asyncpg.Connection,
    conversation_id: UUID,
    call_id: UUID,
    muted: bool,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptMutesResponse:
    """Create an attempt_mutes entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_mutes_entry (id, conversation_id, call_id, muted, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        conversation_id,
        call_id,
        muted,
        not soft,
        mcp,
        id,
    )
    return CreateAttemptMutesResponse(id=entry_id)
