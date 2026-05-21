"""Sessions CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.sessions.types import CreateSessionResponse


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
    entry_id = await conn.fetchval(
        """
        INSERT INTO sessions_entry (id, active, mcp, generated, created_at)
        VALUES (COALESCE($3, uuidv7()), $1, $2, true, COALESCE($4, NOW()))
        RETURNING id
    """,
        not soft,
        mcp,
        id,
        created_at,
    )

    if entry_id is None:
        raise ValueError("Failed to create sessions entry")

    if profile_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_sessions_connection (profiles_id, session_id)
            VALUES ($1, $2)
        """,
            profile_id,
            entry_id,
        )

    return CreateSessionResponse(id=entry_id)
