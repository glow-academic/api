"""Emulations CREATE — insert into emulations_entry with profile link."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.emulations.types import CreateEmulationResponse


async def create_emulation(
    conn: asyncpg.Connection,
    redis: Redis,
    grant_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    profile_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateEmulationResponse:
    """Create an emulation entry and optionally link to a profile."""
    emulation_id = await conn.fetchval(
        """
        INSERT INTO emulations_entry (id, grant_id, session_id, active, mcp, generated, created_at)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true, COALESCE($6, NOW()))
        RETURNING id
        """,
        grant_id,
        session_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    if emulation_id is None:
        raise ValueError("Failed to create emulation entry")

    if profile_id is not None:
        await conn.execute(
            """
            INSERT INTO profiles_emulations_connection (profiles_id, emulation_id)
            VALUES ($1, $2)
            """,
            profile_id,
            emulation_id,
        )

    return CreateEmulationResponse(id=emulation_id)
