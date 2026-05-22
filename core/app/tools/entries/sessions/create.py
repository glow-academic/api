"""Sessions CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.sessions.types import CreateSessionResponse
from app.utils.cache.hedged_row import write_back_row


async def create_session(
    conn: asyncpg.Connection,
    redis: Redis,
    profile_id: UUID | None = None,
    *,
    id: UUID | None = None,
    created_at: datetime | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateSessionResponse:
    """Create a sessions entry with profile link via connection table."""
    row = await conn.fetchrow(
        """
        INSERT INTO sessions_entry (id, active, mcp, generated, created_at)
        VALUES (COALESCE($3, uuidv7()), $1, $2, true, COALESCE($4, NOW()))
        RETURNING id, created_at
    """,
        not soft,
        mcp,
        id,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create sessions entry")

    entry_id = row["id"]
    actual_created_at = row["created_at"]

    if profile_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_sessions_connection (profiles_id, session_id)
            VALUES ($1, $2)
        """,
            profile_id,
            entry_id,
        )

    if profile_id is not None:
        fresh_row = {
            "id": str(entry_id),
            "profile_id": str(profile_id),
            "created_at": actual_created_at.isoformat(),
            "active": not soft,
            "mcp": mcp,
        }
        await write_back_row(
            redis,
            "sessions",
            entry_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    return CreateSessionResponse(id=entry_id)
