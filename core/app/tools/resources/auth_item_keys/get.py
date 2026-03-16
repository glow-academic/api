"""Auth Item Keys Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.auth_item_keys.types import GetAuthItemKeyResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_auth_item_keys(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetAuthItemKeyResponse]:
    """Fetch auth_item_keys_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "auth_item_keys"]
    key = cache_key(
        "/v5/resources/auth_item_keys/get", {"ids": [str(id) for id in ids]}
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetAuthItemKeyResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, auth_id, key_id, item_id,
               created_at, updated_at, active, mcp, generated
        FROM auth_item_keys_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetAuthItemKeyResponse(
            id=r["id"],
            auth_id=r["auth_id"],
            key_id=r["key_id"],
            item_id=r["item_id"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
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
