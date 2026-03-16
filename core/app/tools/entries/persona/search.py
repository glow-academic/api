"""Persona search — filtered/paginated query against persona_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.persona.types import GetPersonaResponse

MV_NAME = "personas_mv"


async def search_personas(
    conn: asyncpg.Connection,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetPersonaResponse]:
    """Search personas from persona_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, active, generated, mcp, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR session_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        session_ids,
        limit,
        offset,
    )

    return [GetPersonaResponse(**dict(r)) for r in rows]
