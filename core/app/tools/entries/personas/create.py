"""Personas CREATE — insert entry + connection table."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.personas.types import CreatePersonasResponse
from app.tools.entries.sessions.create import create_session


async def create_personas(
    conn: asyncpg.Connection,
    id: UUID | None = None,
    session_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    persona_ids: list[UUID] | None = None,
) -> CreatePersonasResponse:
    """Create a personas entry with optional persona connections."""
    if session_id is None:
        session = await create_session(conn, mcp=mcp, soft=soft)
        session_id = session.id

    entry_id = await conn.fetchval(
        """
        INSERT INTO personas_entry (id, session_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, true)
        RETURNING id
    """,
        session_id,
        not soft,
        mcp,
        id,
    )

    if entry_id is None:
        raise ValueError("Failed to create personas entry")

    for pid in persona_ids or []:
        await conn.execute(
            "INSERT INTO personas_personas_connection (personas_entry_id, personas_id) VALUES ($1, $2)",
            entry_id,
            pid,
        )

    return CreatePersonasResponse(id=entry_id)
