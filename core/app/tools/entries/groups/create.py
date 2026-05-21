"""Groups CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.groups.types import CreateGroupResponse


async def create_group(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    *,
    artifact_type: str,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateGroupResponse:
    """Create a groups entry.

    Group naming is handled separately via group_names_entry.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO groups_entry (id, session_id, active, mcp, generated, artifact_type, created_at)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true, $5, COALESCE($6, NOW()))
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, (xmax = 0) AS inserted
    """,
        session_id,
        not soft,
        mcp,
        id,
        artifact_type,
        created_at,
    )

    if row is None or row["id"] is None:
        raise ValueError("Failed to create groups entry")

    # ``xmax = 0`` distinguishes a fresh INSERT from an ON CONFLICT
    # update — Postgres internal column. True ⇒ row was just inserted;
    # False ⇒ row existed and we hit the upsert path. Callers use this
    # to decide whether to load history (existing rows have content
    # worth fetching; freshly-inserted ones are empty).
    return CreateGroupResponse(id=row["id"], inserted=row["inserted"])
