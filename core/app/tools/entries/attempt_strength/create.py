"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_strength.types import (
    CreateAttemptStrengthResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_strength(
    conn: asyncpg.Connection,
    redis: Redis,
    grade_id: UUID,
    message_id: UUID,
    session_id: UUID,
    name: str,
    id: UUID | None = None,
    description: str = "No description provided",
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptStrengthResponse:
    """Create an attempt_strength entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_strength_entry (id, grade_id, message_id, session_id, name, description, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        RETURNING id, created_at
        """,
        grade_id,
        message_id,
        session_id,
        name,
        description,
        not soft,
        mcp,
        id,
    )
    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "strength_id": str(entry_id),
        "message_id": str(message_id),
        "grade_id": str(grade_id),
        "name": name,
        "description": description,
        "created_at": created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "attempt_strength",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateAttemptStrengthResponse(id=entry_id)
