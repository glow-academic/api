"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_replacement.types import (
    CreateAttemptReplacementResponse,
)


async def create_attempt_replacement(
    conn: asyncpg.Connection,
    improvement_id: UUID,
    call_id: UUID,
    section: str,
    replace: str,
    id: UUID | None = None,
    idx: int = 0,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptReplacementResponse:
    """Create an attempt_replacement entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_replacement_entry (id, improvement_id, call_id, section, "replace", idx, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        improvement_id,
        call_id,
        section,
        replace,
        idx,
        not soft,
        mcp,
        id,
    )
    return CreateAttemptReplacementResponse(id=entry_id)
