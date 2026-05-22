"""Attempt practice CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_practice.types import (
    CreateAttemptPracticeResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_practice(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_id: UUID,
    practice_id: UUID,
    session_id: UUID,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptPracticeResponse:
    """Create an attempt_practice_entry bridge row."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_practice_entry (attempt_id, practice_id, session_id, active, mcp, generated, created_at)
        VALUES ($1, $2, $3, $4, $5, true, COALESCE($6, NOW()))
        RETURNING created_at
        """,
        attempt_id,
        practice_id,
        session_id,
        not soft,
        mcp,
        created_at,
    )
    actual_created_at = row["created_at"] if row else created_at

    # Composite cache key: bridge table has no singular id; (attempt_id, practice_id) is the natural row key.
    composite_id = f"{attempt_id}:{practice_id}"
    fresh_row = {
        "id": composite_id,
        "attempt_id": str(attempt_id),
        "practice_id": str(practice_id),
        "session_id": str(session_id),
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
        "active": not soft,
        "generated": True,
        "mcp": mcp,
    }
    if actual_created_at is not None:
        await write_back_row(
            redis,
            "attempt_practice",
            composite_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    return CreateAttemptPracticeResponse(attempt_id=attempt_id, practice_id=practice_id)
