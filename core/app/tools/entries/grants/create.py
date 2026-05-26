"""Grants CREATE — reusable data-access layer."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.grants.types import CreateGrantResponse
from app.utils.cache.hedged_row import write_back_row


async def create_grant(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    id: UUID | None = None,
    expires_at: datetime | None = None,
    profiles_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateGrantResponse:
    """Create a grants entry with optional profile link.

    ``profiles_id`` is the profiles_resource.id (parent resource).
    Defaults to 1 hour expiry if not specified.
    """
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(hours=1)

    row = await conn.fetchrow(
        """
        INSERT INTO grants_entry (id, session_id, expires_at, active, mcp, generated, created_at)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true, COALESCE($6, NOW()))
        RETURNING id, created_at, expires_at, active, mcp
        """,
        session_id,
        expires_at,
        not soft,
        mcp,
        id,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create grants entry")
    grant_id = row["id"]
    actual_created_at = row["created_at"]

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

    fresh_row = {
        "id": str(grant_id),
        "session_id": str(session_id),
        "expires_at": row["expires_at"].isoformat(),
        "created_at": actual_created_at.isoformat(),
        "active": row["active"],
        "generated": True,
        "mcp": row["mcp"],
        "profiles_id": str(profiles_id) if profiles_id else None,
    }
    await write_back_row(
        redis,
        "grants",
        grant_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateGrantResponse(id=grant_id)
