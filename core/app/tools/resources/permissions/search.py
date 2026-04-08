"""Permissions SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.permissions.get import get_permissions
from app.tools.resources.permissions.types import GetPermissionResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def search_permissions(
    conn: asyncpg.Connection,
    redis: Redis,
    artifact: str | None = None,
    operation: str | None = None,
    search: str | None = None,
    limit_count: int = 1000,
    offset_count: int = 0,
    bypass_cache: bool = False,
) -> list[GetPermissionResponse]:
    """Search permissions with optional artifact/operation filters."""
    if limit_count <= 0:
        return []

    tags = ["resources", "permissions"]
    key = cache_key(
        "/resources/permissions/search",
        {
            "artifact": artifact,
            "operation": operation,
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetPermissionResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    conditions = ["active = true"]
    params: list = []
    idx = 1

    if artifact:
        conditions.append(f"artifact = ${idx}::artifact_type")
        params.append(artifact)
        idx += 1

    if operation:
        conditions.append(f"operation = ${idx}::operation_type")
        params.append(operation)
        idx += 1

    if search:
        conditions.append(f"(name ILIKE ${idx} OR artifact::text ILIKE ${idx} OR operation::text ILIKE ${idx})")
        params.append(f"%{search}%")
        idx += 1

    where = " AND ".join(conditions)
    params.extend([limit_count, offset_count])

    rows = await conn.fetch(
        f"""
        SELECT id
        FROM permissions_resource
        WHERE {where}
        ORDER BY artifact, operation
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )

    if not rows:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    ids = [r["id"] for r in rows]
    items = await get_permissions(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
