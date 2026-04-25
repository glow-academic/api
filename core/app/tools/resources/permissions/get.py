"""Permissions Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.permissions.types import GetPermissionResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_permissions(
    pool_or_conn: asyncpg.Pool | asyncpg.Connection,
    ids: list[UUID] | None,
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetPermissionResponse]:
    """Fetch permissions_resource entries by IDs (or all if ids is None).

    Accepts either a Pool or a Connection — see get_names for rationale.
    """
    tags = ["resources", "permissions"]

    if ids is not None and not ids:
        return []

    key = cache_key(
        "/resources/permissions/get",
        {"ids": [str(id) for id in ids] if ids else ["all"]},
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetPermissionResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    if ids is not None:
        sql = """
            SELECT id, artifact::text, operation::text, name, description,
                   active, generated, mcp, created_at
            FROM permissions_resource
            WHERE id = ANY($1)
            ORDER BY array_position($1, id)
            """
        args = (ids,)
    else:
        sql = """
            SELECT id, artifact::text, operation::text, name, description,
                   active, generated, mcp, created_at
            FROM permissions_resource
            WHERE active = true
            ORDER BY artifact, operation
            """
        args = ()

    if isinstance(pool_or_conn, asyncpg.Pool):
        async with pool_or_conn.acquire() as conn:
            rows = await conn.fetch(sql, *args)
    else:
        rows = await pool_or_conn.fetch(sql, *args)
    items = [
        GetPermissionResponse(
            id=r["id"],
            artifact=r["artifact"],
            operation=r["operation"],
            name=r["name"],
            description=r["description"],
            active=r["active"],
            generated=r["generated"],
            mcp=r["mcp"],
            created_at=r["created_at"],
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
