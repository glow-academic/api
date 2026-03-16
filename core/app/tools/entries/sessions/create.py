"""Sessions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.sessions.types import CreateSessionResponse


async def create_session(
    conn: asyncpg.Connection,
    profile_id: UUID | None = None,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateSessionResponse:
    """Create a sessions entry with profile link via connection table."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO sessions_entry (id, active, mcp, generated)
        VALUES (COALESCE($3, uuidv7()), $1, $2, true)
        RETURNING id
    """,
        not soft,
        mcp,
        id,
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
