"""Fields Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.fields.types import GetFieldResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_fields(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetFieldResponse]:
    """Fetch fields_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "fields"]
    key = cache_key("/v5/resources/fields/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetFieldResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, value,
               department_ids, conditional_parameter_ids,
               created_at, active, generated, mcp
        FROM fields_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetFieldResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            value=r["value"],
            department_ids=r["department_ids"] or [],
            conditional_parameter_ids=r["conditional_parameter_ids"] or [],
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
