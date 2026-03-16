"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_highlight.types import (
    CreateAttemptHighlightResponse,
)


async def create_attempt_highlight(
    conn: asyncpg.Connection,
    strength_id: UUID,
    call_id: UUID,
    section: str,
    id: UUID | None = None,
    idx: int = 0,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptHighlightResponse:
    """Create an attempt_highlight entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_highlight_entry (id, strength_id, call_id, section, idx, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true)
        RETURNING id
        """,
        strength_id,
        call_id,
        section,
        idx,
        not soft,
        mcp,
        id,
    )
    return CreateAttemptHighlightResponse(id=entry_id)
