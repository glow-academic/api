"""Primary Departments Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.primary_departments.types import (
    GetPrimaryDepartmentResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_primary_departments(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetPrimaryDepartmentResponse]:
    """Fetch primary_departments_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "primary_departments"]
    key = cache_key(
        "/resources/primary_departments/get",
        {"ids": [str(id) for id in ids]},
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetPrimaryDepartmentResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, departments_id, created_at, active, generated, mcp
        FROM primary_departments_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
        """,
        ids,
    )

    items = [
        GetPrimaryDepartmentResponse(
            id=r["id"],
            departments_id=r["departments_id"],
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
