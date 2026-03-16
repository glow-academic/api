"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_improvement.types import (
    CreateAttemptImprovementResponse,
)


async def create_attempt_improvement(
    conn: asyncpg.Connection,
    grade_id: UUID,
    message_id: UUID,
    call_id: UUID,
    name: str,
    id: UUID | None = None,
    description: str = "No description provided",
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptImprovementResponse:
    """Create an attempt_improvement entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_improvement_entry (id, grade_id, message_id, call_id, name, description, active, mcp, generated)
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
    return CreateAttemptImprovementResponse(id=entry_id)
