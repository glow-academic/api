"""Departments Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.departments.types import GetDepartmentResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_departments(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetDepartmentResponse]:
    """Fetch departments_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "departments"]
    key = cache_key(
        "/v5/resources/departments/get", {"ids": [str(id) for id in ids]}
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetDepartmentResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, department_ids, setting_ids,
               is_primary, created_at, active, mcp, generated
        FROM departments_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetDepartmentResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            department_ids=r["department_ids"] or [],
            setting_ids=r["setting_ids"] or [],
            is_primary=r["is_primary"],
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
