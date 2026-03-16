"""Activity CREATE — insert into activity_entry with profile link."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.activity.types import CreateActivityResponse


async def create_activity(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    profile_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateActivityResponse:
    """Create an activity entry and optionally link to a profile."""
    activity_id = await conn.fetchval(
        """
        INSERT INTO activity_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id
        """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if activity_id is None:
        raise ValueError("Failed to create activity entry")

    if profile_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_activity_connection (profiles_id, activity_id)
            VALUES ($1, $2)
            """,
            profile_id,
            activity_id,
        )

    return CreateActivityResponse(id=activity_id)
