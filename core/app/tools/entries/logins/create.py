"""Logins CREATE — insert into logins_entry with profile link."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.logins.types import CreateLoginResponse


async def create_login(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    id: UUID | None = None,
    profile_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateLoginResponse:
    """Create a login entry and optionally link to a profile."""
    login_id = await conn.fetchval(
        """
        INSERT INTO logins_entry (id, session_id, active, mcp, generated, created_at)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true, COALESCE($5, NOW()))
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    if login_id is None:
        raise ValueError("Failed to create login entry")

    if profile_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_logins_connection (profiles_id, login_id)
            VALUES ($1, $2)
            """,
            profile_id,
            login_id,
        )

    return CreateLoginResponse(id=login_id)
