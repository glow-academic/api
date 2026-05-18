"""Mcp SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.mcp.get import get_mcp
from app.tools.resources.mcp.types import GetMcpResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def search_mcp(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    agent_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
) -> list[GetMcpResponse]:
    """Search mcp_resource with optional agent_ids filter."""
    if limit_count <= 0:
        return []

    tags = ["resources", "mcp"]
    key = cache_key(
        "/resources/mcp/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "agent_ids": sorted(str(i) for i in (agent_ids or [])),
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetMcpResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    conditions = ["active = true"]
    params: list[object] = []
    idx = 1

    if search:
        conditions.append(f"(name ILIKE ${idx} OR description ILIKE ${idx})")
        params.append(f"%{search}%")
        idx += 1

    if exclude_ids:
        conditions.append(f"id != ALL(${idx}::uuid[])")
        params.append(exclude_ids)
        idx += 1

    if agent_ids:
        conditions.append(f"agent_id = ANY(${idx}::uuid[])")
        params.append(agent_ids)
        idx += 1

    where = " AND ".join(conditions)
    query = f"""
        SELECT id
        FROM mcp_resource
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT {limit_count} OFFSET {offset_count}
    """

    rows = await conn.fetch(query, *params)
    ids = [r["id"] for r in rows]

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_mcp(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
