"""Mcp CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.mcp.get import get_mcp
from app.tools.resources.mcp.types import GetMcpResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_mcp(
    conn: asyncpg.Connection,
    agent_id: UUID,
    name: str = "",
    description: str = "",
    id: UUID | None = None,
    mcp: bool = False,
    redis: Redis = None,
    soft: bool = False,
) -> GetMcpResponse:
    """Create an mcp resource (plain INSERT — no unique constraint)."""
    mcp_id = await conn.fetchval(
        """
        INSERT INTO mcp_resource (id, agent_id, name, description, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5)
        RETURNING id
        """,
        agent_id,
        name,
        description,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "mcp"], redis=redis)
    items = await get_mcp(conn, [mcp_id], redis, bypass_cache=True)
    return items[0]
