"""Sessions GET internal function — delegates to search_sessions black box.

Used internally by profile context to resolve the most recent session.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.sessions.search import search_sessions
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_session_impl(
    conn: asyncpg.Connection,
    profile_id: UUID,
    *,
    redis: Redis | None = None,
    bypass_cache: bool = False,
) -> UUID | None:
    """Fetch the most recent active session for a profile.

    Composes search_sessions black box — no inline SQL.
    """
    cache_redis = redis or _get_redis()
    tags = ["infra", "sessions"]
    cache_key_val = cache_key(
        "infra/sessions/get",
        {"profile_id": str(profile_id)},
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=cache_redis)
        if cached is not None:
            sid = cached.get("session_id")
            return UUID(sid) if sid else None

    results = await search_sessions(
        conn,
        profile_ids=[profile_id],
        active=True,
        limit=1,
    )

    session_id = results[0].id if results else None

    await set_cached(
        cache_key_val,
        {"session_id": str(session_id) if session_id else None},
        ttl=60,
        tags=tags,
        redis=cache_redis,
    )

    return session_id


def _get_redis():
    from app.infra.globals import get_redis_client

    return get_redis_client()
