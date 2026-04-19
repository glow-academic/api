"""Logins Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.logins.types import GetLoginsResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_logins(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetLoginsResponse]:
    """Fetch logins_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "logins"]
    key = cache_key("/resources/logins/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetLoginsResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, profile_id, auth_id, icon_id, display_name, login_type,
               created_at, active, generated, mcp
        FROM logins_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetLoginsResponse(
            id=r["id"],
            profile_id=r["profile_id"],
            auth_id=r["auth_id"],
            icon_id=r["icon_id"],
            display_name=r["display_name"],
            login_type=r["login_type"],
            created_at=r["created_at"],
            active=r["active"],
            generated=r["generated"],
            mcp=r["mcp"],
        )
        for r in rows
    ]

    if not bypass_cache:
        await set_cached(
            key,
            {"items": [i.model_dump(mode="json") for i in items]},
            60,
            tags,
            redis=redis,
        )
    return items
