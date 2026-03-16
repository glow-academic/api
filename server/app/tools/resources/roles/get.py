"""Roles Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.roles.types import GetRoleResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_roles(
    conn: asyncpg.Connection,
    ids: list[UUID] | None,
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetRoleResponse]:
    """Fetch roles_resource entries by IDs, or all if ids is None."""
    if ids is not None and not ids:
        return []

    tags = ["resources", "roles"]
    cache_ids = sorted(str(i) for i in ids) if ids else ["__all__"]
    key = cache_key("/v5/resources/roles/get", {"ids": cache_ids})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetRoleResponse.model_validate(item) for item in cached.get("items", [])
            ]

    if ids is not None:
        rows = await conn.fetch(
            """
            SELECT id, role, name, description, icon_id, color_id,
                   artifacts, created_at, active, generated, mcp
            FROM roles_resource
            WHERE id = ANY($1)
            ORDER BY array_position($1, id)
        """,
            ids,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, role, name, description, icon_id, color_id,
                   artifacts, created_at, active, generated, mcp
            FROM roles_resource
            ORDER BY created_at
        """,
        )

    items = [
        GetRoleResponse(
            id=r["id"],
            role=r["role"],
            name=r["name"],
            description=r["description"],
            icon_id=r["icon_id"],
            color_id=r["color_id"],
            artifacts=[str(a) for a in (r["artifacts"] or [])],
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
            300,
            tags,
            redis=redis,
        )
    return items
