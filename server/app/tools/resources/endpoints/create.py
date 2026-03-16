"""Endpoints CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.endpoints.get import get_endpoints
from app.tools.resources.endpoints.types import GetEndpointResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_endpoint(
    conn: asyncpg.Connection,
    base_url: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetEndpointResponse:
    """Create an endpoint resource."""
    endpoint_id = await conn.fetchval(
        """
        INSERT INTO endpoints_resource (id, base_url, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        ON CONFLICT (base_url) WHERE active = true DO UPDATE SET base_url = EXCLUDED.base_url
        RETURNING id
    """,
        base_url,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "endpoints"], redis=redis)
    items = await get_endpoints(conn, [endpoint_id], redis, bypass_cache=True)
    return items[0]
