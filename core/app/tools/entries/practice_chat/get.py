"""practice_chat/get — reusable data-access layer."""

import json
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.globals import get_redis_client
from app.tools.entries.practice_chat.types import GetPracticeChatResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.hedged_row import read_back_row
from app.utils.cache.set_cached import set_cached

MV_NAME = "practice_chat_mv"


async def get_practice_chats(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetPracticeChatResponse]:
    """Get practice_chat entries by IDs from practice_chat_mv."""
    if not ids:
        return []

    cached_results: dict[str, GetPracticeChatResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "practice_chat", rid)
            if cached is not None:
                cached_results[str(rid)] = GetPracticeChatResponse.model_validate(cached)
            else:
                missing_ids.append(rid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetPracticeChatResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"""
            SELECT id, practice_id, chat_id, created_at, active, generated, mcp, session_id
            FROM {MV_NAME}
            WHERE id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetPracticeChatResponse(
                id=r["id"],
                practice_id=r["practice_id"],
                chat_id=r["chat_id"],
                created_at=r["created_at"],
                active=r["active"],
                generated=r["generated"],
                mcp=r["mcp"],
                session_id=r["session_id"],
            )

    out: list[GetPracticeChatResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out


async def get_practice_chat_entries_internal(
    pool_or_conn: asyncpg.Pool | asyncpg.Connection,
    ids: list[UUID],
    bypass_cache: bool = False,
) -> list[dict]:
    """Internal function to fetch practice_chat entries by IDs.

    Accepts either a Pool or a Connection — see get_names for rationale.
    """
    if not ids:
        return []

    tags = ["entries", "practice_chat"]
    cache_key_val = cache_key(
        "/entries/practice_chat/get",
        {"ids": [str(id) for id in ids]},
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return list(cached.get("items", []))

    sql = """
        SELECT COALESCE(jsonb_agg(jsonb_build_object(
            'id', m.id,
            'practice_id', m.practice_id,
            'chat_id', m.chat_id,
            'created_at', m.created_at,
            'active', m.active,
            'generated', m.generated,
            'mcp', m.mcp
        )), '[]'::jsonb)
        FROM practice_chat_mv m
        WHERE m.id = ANY($1)
        """
    if isinstance(pool_or_conn, asyncpg.Pool):
        async with pool_or_conn.acquire() as conn:
            result = await conn.fetchval(sql, ids)
    else:
        result = await pool_or_conn.fetchval(sql, ids)

    items: list[dict] = (
        json.loads(result) if isinstance(result, str) else (result or [])
    )

    await set_cached(
        cache_key_val,
        {"items": items if isinstance(items, list) else []},
        ttl=60,
        tags=tags,
        redis=get_redis_client(),
    )

    return items
