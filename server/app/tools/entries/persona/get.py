"""persona/get internal — reusable data-access layer."""

import json
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.globals import get_redis_client
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_persona_entries_internal(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_cache: bool = False,
) -> list[dict]:
    """Internal function to fetch persona entries by IDs."""
    if not ids:
        return []

    tags = ["entries", "persona"]
    cache_key_val = cache_key(
        "/v5/entries/persona/get",
        {"ids": [str(id) for id in ids]},
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return list(cached.get("items", []))

    result = await conn.fetchval(
        """
        SELECT COALESCE(jsonb_agg(jsonb_build_object(
            'id', m.id,
            'chat_id', m.chat_id,
            'created_at', m.created_at,
            'updated_at', m.updated_at,
            'active', m.active,
            'generated', m.generated,
            'mcp', m.mcp
        )), '[]'::jsonb)
        FROM persona_mv m
        WHERE m.id = ANY($1)
        """,
        ids,
    )

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
