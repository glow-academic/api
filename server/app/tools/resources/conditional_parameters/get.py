"""Conditional Parameters Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.conditional_parameters.types import (
    GetConditionalParameterResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_conditional_parameters(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetConditionalParameterResponse]:
    """Fetch conditional_parameters_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "conditional_parameters"]
    key = cache_key(
        "/v5/resources/conditional_parameters/get", {"ids": [str(id) for id in ids]}
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetConditionalParameterResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, parameter_id,
               created_at, updated_at, active, generated, mcp
        FROM conditional_parameters_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetConditionalParameterResponse(
            id=r["id"],
            parameter_id=r["parameter_id"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
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
