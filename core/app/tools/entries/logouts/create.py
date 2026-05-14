"""Logouts CREATE — insert into logouts_entry with profile link."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.logouts.types import CreateLogoutResponse


async def create_logout(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    profile_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateLogoutResponse:
    """Create a logout entry and optionally link to a profile."""
    logout_id = await conn.fetchval(
        """
        INSERT INTO logouts_entry (id, session_id, active, mcp, generated, created_at)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true, COALESCE($5, NOW()))
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    if logout_id is None:
        raise ValueError("Failed to create logout entry")

    if profile_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_logouts_connection (profiles_id, logout_id)
            VALUES ($1, $2)
            """,
            profile_id,
            logout_id,
        )

    return CreateLogoutResponse(id=logout_id)
