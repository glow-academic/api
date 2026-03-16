"""Flags Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.flags.types import GetFlagResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_flags(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetFlagResponse]:
    """Fetch flags_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "flags"]
    key = cache_key("/v5/resources/flags/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetFlagResponse.model_validate(item) for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, type, icon,
               created_at, active, mcp, generated, value
        FROM flags_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetFlagResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            type=r["type"],
            icon=r["icon"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
            value=r["value"],
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
