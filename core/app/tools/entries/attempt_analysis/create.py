"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_analysis.types import (
    CreateAttemptAnalysisResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_analysis(
    conn: asyncpg.Connection,
    redis: Redis,
    grade_id: UUID,
    session_id: UUID,
    content: str,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptAnalysisResponse:
    """Create an attempt_analysis entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_analysis_entry (id, grade_id, session_id, content, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id, created_at
        """,
        grade_id,
        session_id,
        content,
        not soft,
        mcp,
        id,
    )
    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "analysis_id": str(entry_id),
        "grade_id": str(grade_id),
        "content": content,
        "created_at": created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "attempt_analysis",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAttemptAnalysisResponse(id=entry_id)
