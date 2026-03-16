"""Logins CREATE — insert into logins_entry with profile link."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.logins.types import CreateLoginResponse


async def create_login(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    profile_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateLoginResponse:
    """Create a login entry and optionally link to a profile."""
    login_id = await conn.fetchval(
        """
        INSERT INTO logins_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        id,
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
