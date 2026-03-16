"""Provider Keys Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.provider_keys.types import GetProviderKeyResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_provider_keys(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetProviderKeyResponse]:
    """Fetch provider_keys_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "provider_keys"]
    key = cache_key(
        "/v5/resources/provider_keys/get", {"ids": [str(id) for id in ids]}
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetProviderKeyResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, provider_id, key_id, key, name, description,
               created_at, active, mcp, generated
        FROM provider_keys_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetProviderKeyResponse(
            id=r["id"],
            provider_id=r["provider_id"],
            key_id=r["key_id"],
            key=r["key"],
            name=r["name"],
            description=r["description"],
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
