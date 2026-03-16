"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_strength.types import (
    CreateAttemptStrengthResponse,
)


async def create_attempt_strength(
    conn: asyncpg.Connection,
    grade_id: UUID,
    message_id: UUID,
    call_id: UUID,
    name: str,
    id: UUID | None = None,
    description: str = "No description provided",
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptStrengthResponse:
    """Create an attempt_strength entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_strength_entry (id, grade_id, message_id, call_id, name, description, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id
        """,
        grade_id,
        message_id,
        call_id,
        name,
        description,
        not soft,
        mcp,
        id,
    )
    return CreateAttemptStrengthResponse(id=entry_id)
