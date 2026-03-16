"""Auth Item Values Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.auth_item_values.types import (
    GetAuthItemValueResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_auth_item_values(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetAuthItemValueResponse]:
    """Fetch auth_item_values_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "auth_item_values"]
    key = cache_key(
        "/v5/resources/auth_item_values/get", {"ids": [str(id) for id in ids]}
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetAuthItemValueResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, auth_id, item_id, value,
               created_at, active, mcp, generated
        FROM auth_item_values_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetAuthItemValueResponse(
            id=r["id"],
            auth_id=r["auth_id"],
            item_id=r["item_id"],
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
