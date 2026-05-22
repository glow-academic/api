"""Persona search — filtered/paginated query against persona_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.persona.types import GetPersonaResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "personas_mv"


async def search_personas(
    conn: asyncpg.Connection,
    redis: Redis,
    session_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
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
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
        }
        for r in rows
    ]

    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def matches(row: dict) -> bool:
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "persona",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetPersonaResponse.model_validate(r) for r in merged]
