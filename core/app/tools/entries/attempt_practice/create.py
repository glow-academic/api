"""Attempt practice CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_practice.types import (
    CreateAttemptPracticeResponse,
)


async def create_attempt_practice(
    conn: asyncpg.Connection,
    attempt_id: UUID,
    practice_id: UUID,
    session_id: UUID,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptPracticeResponse:
    """Create an attempt_practice_entry bridge row."""
    await conn.execute(
        """
        INSERT INTO attempt_practice_entry (attempt_id, practice_id, session_id, active, mcp, generated, created_at)
        VALUES ($1, $2, $3, $4, $5, true, COALESCE($6, NOW()))
        """,
        attempt_id,
        practice_id,
        session_id,
        not soft,
        mcp,
        created_at,
    )

    return CreateAttemptPracticeResponse(attempt_id=attempt_id, practice_id=practice_id)
