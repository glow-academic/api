"""Personas CREATE — insert entry + connection table."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.personas.types import CreatePersonasResponse
from app.tools.entries.sessions.create import create_session
from app.utils.cache.hedged_row import write_back_row


async def create_personas(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    session_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    persona_ids: list[UUID] | None = None,
) -> CreatePersonasResponse:
    """Create a personas entry with optional persona connections."""
    if session_id is None:
        session = await create_session(conn, redis, mcp=mcp, soft=soft)
        session_id = session.id

    row = await conn.fetchrow(
        """
        INSERT INTO personas_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id, created_at, active, mcp
    """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if row is None:
        raise ValueError("Failed to create personas entry")
    entry_id = row["id"]
    created_at = row["created_at"]
    active_val = row["active"]
    mcp_val = row["mcp"]

    for pid in persona_ids or []:
        await conn.execute(
            "INSERT INTO personas_personas_connection (personas_entry_id, personas_id) VALUES ($1, $2)",
            entry_id,
            pid,
        )

    fresh_row = {
        "id": str(entry_id),
        "created_at": created_at.isoformat(),
        "active": active_val,
        "generated": True,
        "mcp": mcp_val,
        "session_id": str(session_id) if session_id else None,
        "persona_ids": [str(p) for p in (persona_ids or [])],
    }
    await write_back_row(
        redis,
        "personas",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreatePersonasResponse(id=entry_id)
