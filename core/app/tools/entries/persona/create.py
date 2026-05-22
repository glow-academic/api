"""Persona CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.persona.types import CreatePersonaResponse
from app.tools.entries.sessions.create import create_session
from app.utils.cache.hedged_row import write_back_row


async def create_persona(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    personas_id: UUID | None = None,
    session_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreatePersonaResponse:
    """Create a personas entry with optional resource link."""
    if session_id is None:
        session = await create_session(conn, redis, mcp=mcp, soft=soft)
        session_id = session.id

    row = await conn.fetchrow(
        """
        INSERT INTO personas_entry (id, active, mcp, generated, session_id)
        VALUES (COALESCE($4, uuidv7()), $1, $2, true, $3)
        RETURNING id, created_at, active, mcp
        """,
        not soft,
        mcp,
        session_id,
        id,
    )

    if row is None:
        raise ValueError("Failed to create personas entry")
    persona_id = row["id"]
    created_at = row["created_at"]
    active_val = row["active"]
    mcp_val = row["mcp"]

    # Link to personas_resource via connection table
    if personas_id is not None:
        await conn.execute(
            """
            INSERT INTO personas_personas_connection (personas_entry_id, personas_id, generated)
            VALUES ($1, $2, true)
            """,
            persona_id,
            personas_id,
        )

    fresh_row = {
        "id": str(persona_id),
        "created_at": created_at.isoformat(),
        "active": active_val,
        "generated": True,
        "mcp": mcp_val,
        "session_id": str(session_id) if session_id else None,
    }
    await write_back_row(
        redis,
        "persona",
        persona_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreatePersonaResponse(id=persona_id)
