"""Grants CREATE — reusable data-access layer."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.grants.types import CreateGrantResponse


async def create_grant(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    expires_at: datetime | None = None,
    profiles_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateGrantResponse:
    """Create a grants entry with optional profile link.

    ``profiles_id`` is the profiles_resource.id (parent resource).
    Defaults to 1 hour expiry if not specified.
    """
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(hours=1)

    grant_id = await conn.fetchval(
        """
        INSERT INTO grants_entry (id, session_id, expires_at, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true)
        RETURNING id
        """,
        session_id,
        expires_at,
        not soft,
        mcp,
        id,
    )

    if grant_id is None:
        raise ValueError("Failed to create grants entry")

    # Link grant → profiles_resource
    if profiles_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_grants_connection (profiles_id, grant_id)
            VALUES ($1, $2)
            """,
            profiles_id,
            grant_id,
        )

    return CreateGrantResponse(id=grant_id)
