"""attempt_mutes/search — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_mutes_mv"


async def search_attempt_mutes_entries_internal(
    conn: asyncpg.Connection,
    redis: Redis,
    conversation_ids: list[UUID] | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[dict]:
    """Search attempt_mutes entries from attempt_mutes_mv."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active,
               conversation_id, muted, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR conversation_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        conversation_ids,
        limit_count + offset_count + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "created_at": r["created_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
            "conversation_id": str(r["conversation_id"]) if r["conversation_id"] else None,
            "muted": r["muted"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
        }
        for r in rows
    ]

    conversation_ids_str = (
        {str(c) for c in conversation_ids} if conversation_ids else None
    )

    def matches(row: dict) -> bool:
        if (
            conversation_ids_str is not None
            and str(row.get("conversation_id")) not in conversation_ids_str
        ):
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_mutes",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit_count,
        offset=offset_count,
        bypass_cache=bypass_cache,
    )
    return merged
