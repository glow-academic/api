"""Personas GET — read from base table + connection table."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.personas.types import GetPersonasResponse
from app.utils.cache.hedged_row import read_back_rows


async def get_personas(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetPersonasResponse]:
    """Get personas entries by IDs with their persona connections."""
    if not ids:
        return []

    cached_results: dict[str, GetPersonasResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        # One pipelined MGET for all ids instead of one GET per id.
        cached_rows = await read_back_rows(redis, "personas", list(ids))
        for did in ids:
            cached = cached_rows.get(str(did))
            if cached is not None:
                # GET filters active=true; honor that on cached rows
                if not cached.get("active", True):
                    continue
                cached_results[str(did)] = GetPersonasResponse.model_validate(cached)
            else:
                missing_ids.append(did)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetPersonasResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            """
            SELECT
                e.id, e.created_at, e.active, e.generated, e.mcp, e.session_id,
                COALESCE(ARRAY_AGG(DISTINCT pc.personas_id) FILTER (WHERE pc.personas_id IS NOT NULL), '{}') AS persona_ids
            FROM personas_entry e
            LEFT JOIN personas_personas_connection pc ON pc.personas_entry_id = e.id
            WHERE e.id = ANY($1) AND e.active = true
            GROUP BY e.id, e.created_at, e.active, e.generated, e.mcp, e.session_id
            ORDER BY e.created_at DESC
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetPersonasResponse(
                id=r["id"],
                created_at=r["created_at"],
                active=r["active"],
                generated=r["generated"],
                mcp=r["mcp"],
                session_id=r["session_id"],
                persona_ids=r["persona_ids"],
            )

    out: list[GetPersonasResponse] = []
    for did in ids:
        key = str(did)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
