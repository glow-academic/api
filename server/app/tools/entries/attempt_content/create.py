"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_content.types import (
    CreateAttemptContentResponse,
)


async def create_attempt_content(
    conn: asyncpg.Connection,
    message_id: UUID,
    call_id: UUID,
    content: str,
    persona_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptContentResponse:
    """Create an attempt_content entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_content_entry
            (id, message_id, call_id, content, persona_id, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true)
        RETURNING id
        """,
        message_id,
        call_id,
        content,
        persona_id,
        not soft,
        mcp,
        id,
    )

    return CreateAttemptContentResponse(id=entry_id)
