"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_hint.types import CreateAttemptHintResponse


async def create_attempt_hint(
    conn: asyncpg.Connection,
    message_id: UUID,
    call_id: UUID,
    hint: str,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptHintResponse:
    """Create an attempt_hint entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_hint_entry
            (id, message_id, call_id, hint, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        message_id,
        call_id,
        hint,
        not soft,
        mcp,
        id,
    )

    return CreateAttemptHintResponse(id=entry_id)
