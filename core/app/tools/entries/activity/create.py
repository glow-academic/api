"""Activity CREATE — insert into activity_entry with profile link."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.activity.types import CreateActivityResponse
from app.utils.cache.hedged_row import write_back_row


async def create_activity(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    id: UUID | None = None,
    profile_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateActivityResponse:
    """Create an activity entry and optionally link to a profile."""
    row = await conn.fetchrow(
        """
        INSERT INTO activity_entry (id, session_id, active, mcp, generated, created_at)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true, COALESCE($5, NOW()))
        RETURNING id, created_at, active, mcp
        """,
        session_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create activity entry")
    activity_id = row["id"]
    actual_created_at = row["created_at"]

    if profile_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_activity_connection (profiles_id, activity_id)
            VALUES ($1, $2)
            """,
            profile_id,
            activity_id,
        )

    fresh_row = {
        "id": str(activity_id),
        "profile_id": str(profile_id) if profile_id else None,
        "session_id": str(session_id) if session_id else None,
        "created_at": actual_created_at.isoformat(),
        "active": row["active"],
        "mcp": row["mcp"],
        "generated": True,
    }
    await write_back_row(
        redis,
        "activity",
        activity_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateActivityResponse(id=activity_id)
