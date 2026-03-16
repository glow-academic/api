"""Slugs Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.slugs.types import GetSlugResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_slugs(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetSlugResponse]:
    """Fetch slugs_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "slugs"]
    key = cache_key("/v5/resources/slugs/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetSlugResponse.model_validate(item) for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, value,
               created_at, active, mcp, generated
        FROM slugs_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetSlugResponse(
            id=r["id"],
            value=r["value"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
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
