"""chat/search — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.utils.cache.hedged_row import hedged_search

MV_NAME = "chat_mv"


async def search_chat_entries_internal(
    conn: asyncpg.Connection,
    redis: Redis,
    parent_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    bypass_cache: bool = False,
) -> list[dict]:
    """Search chat entries from chat_mv (with cache hedge).

    Returns ``list[dict]`` for backward compat with the export/context
    callers that iterate via dict access. Cache row carries both the
    canonical GET-shape keys (used by ``get_chats``) and the SEARCH-shape
    keys (chat_entry_id/session_id/name/description/created_at/active);
    hedged_search merges cache and MV slices by ``chat_entry_id``.
    """
    rows = await conn.fetch(
        f"""
        SELECT chat_entry_id, parent_id, session_id, scenario_id, name, description,
               department_ids, persona_ids, created_at, active
        FROM {MV_NAME}
        WHERE ($1::uuid[] IS NULL OR parent_id = ANY($1))
          AND ($2::uuid[] IS NULL OR session_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        parent_ids,
        session_ids,
        limit_count + offset_count + 1000,
        0,
    )

    mv_dicts = [
        {
            "chat_entry_id": str(r["chat_entry_id"]),
            "parent_id": str(r["parent_id"]) if r["parent_id"] else None,
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "scenario_id": str(r["scenario_id"]) if r["scenario_id"] else None,
            "name": r["name"],
            "description": r["description"],
            "department_ids": [str(x) for x in (r["department_ids"] or [])],
            "persona_ids": [str(x) for x in (r["persona_ids"] or [])],
            "created_at": r["created_at"],
            "active": r["active"],
        }
        for r in rows
    ]

    parent_ids_str = {str(p) for p in parent_ids} if parent_ids else None
    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def matches(row: dict) -> bool:
        if parent_ids_str is not None:
            if str(row.get("parent_id")) not in parent_ids_str:
                return False
        if session_ids_str is not None:
            if str(row.get("session_id")) not in session_ids_str:
                return False
        return True

    merged = await hedged_search(
        redis,
        "chat",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit_count,
        offset=offset_count,
        id_key="chat_entry_id",
        bypass_cache=bypass_cache,
    )
    # Project cache-row supersets down to the legacy search-dict shape.
    out_keys = {
        "chat_entry_id", "parent_id", "session_id", "scenario_id",
        "name", "description", "department_ids", "persona_ids",
        "created_at", "active",
    }
    return [{k: r.get(k) for k in out_keys} for r in merged]
