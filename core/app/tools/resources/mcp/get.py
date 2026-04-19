"""Mcp Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.mcp.types import GetMcpResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_mcp(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetMcpResponse]:
    """Fetch mcp_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "mcp"]
    key = cache_key("/resources/mcp/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetMcpResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, agent_id, name, description,
               created_at, active, generated, mcp
        FROM mcp_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetMcpResponse(
            id=r["id"],
            agent_id=r["agent_id"],
            name=r["name"],
            description=r["description"],
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
