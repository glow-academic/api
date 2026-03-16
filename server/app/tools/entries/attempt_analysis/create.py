"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_analysis.types import (
    CreateAttemptAnalysisResponse,
)


async def create_attempt_analysis(
    conn: asyncpg.Connection,
    grade_id: UUID,
    call_id: UUID,
    content: str,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptAnalysisResponse:
    """Create an attempt_analysis entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_analysis_entry (id, grade_id, call_id, content, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        grade_id,
        call_id,
        content,
        not soft,
        mcp,
        id,
    )
    return CreateAttemptAnalysisResponse(id=entry_id)
