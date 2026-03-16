"""Standard Groups Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.standard_groups.types import GetStandardGroupResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_standard_groups(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetStandardGroupResponse]:
    """Fetch standard_groups_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "standard_groups"]
    key = cache_key(
        "/v5/resources/standard_groups/get", {"ids": [str(id) for id in ids]}
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetStandardGroupResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, short_name, description, points, pass_points,
               created_at, active, generated, mcp
        FROM standard_groups_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetStandardGroupResponse(
            id=r["id"],
            name=r["name"],
            short_name=r["short_name"],
            description=r["description"],
            points=r["points"],
            pass_points=r["pass_points"],
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
