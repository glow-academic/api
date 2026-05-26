"""home_chat/get — reusable data-access layer."""

import json
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.globals import get_redis_client
from app.tools.entries.home_chat.types import GetHomeChatResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.hedged_row import read_back_row
from app.utils.cache.set_cached import set_cached

MV_NAME = "home_chat_mv"


async def get_home_chats(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetHomeChatResponse]:
    """Get home_chat entries by IDs from home_chat_mv."""
    if not ids:
        return []

    cached_results: dict[str, GetHomeChatResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for hid in ids:
            cached = await read_back_row(redis, "home_chat", hid)
            if cached is not None:
                cached_results[str(hid)] = GetHomeChatResponse.model_validate(cached)
            else:
                missing_ids.append(hid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetHomeChatResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"""
            SELECT id, home_id, chat_id, created_at, active, generated, mcp, session_id
            FROM {MV_NAME}
            WHERE id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetHomeChatResponse(
                id=r["id"],
                home_id=r["home_id"],
                chat_id=r["chat_id"],
                created_at=r["created_at"],
                active=r["active"],
                generated=r["generated"],
                mcp=r["mcp"],
                session_id=r["session_id"],
            )

    out: list[GetHomeChatResponse] = []
    for hid in ids:
        key = str(hid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out


async def get_home_chat_entries_internal(
    pool_or_conn: asyncpg.Pool | asyncpg.Connection,
    ids: list[UUID],
    bypass_cache: bool = False,
) -> list[dict]:
    """Internal function to fetch home_chat entries by IDs.

    Accepts either a Pool or a Connection — see get_names for rationale.
    """
    if not ids:
        return []

    tags = ["entries", "home_chat"]
    cache_key_val = cache_key(
        "/entries/home_chat/get",
        {"ids": [str(id) for id in ids]},
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return list(cached.get("items", []))

    sql = """
        SELECT COALESCE(jsonb_agg(jsonb_build_object(
            'id', m.id,
            'home_id', m.home_id,
            'chat_id', m.chat_id,
            'created_at', m.created_at,
            'active', m.active,
            'generated', m.generated,
            'mcp', m.mcp
        )), '[]'::jsonb)
        FROM home_chat_mv m
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
