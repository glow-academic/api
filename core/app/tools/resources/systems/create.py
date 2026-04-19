"""Systems CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.systems.get import get_systems
from app.tools.resources.systems.types import GetSystemResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_system(
    conn: asyncpg.Connection,
    name: str = "",
    description: str = "",
    redis: Redis = None,
    agent_ids: list[UUID] | None = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    resolution_strategy: str | None = None,
    resolution_threshold: float | None = None,
) -> GetSystemResponse:
    """Create a system resource (plain INSERT — no unique constraint)."""
    system_id = await conn.fetchval(
        """
        INSERT INTO systems_resource (id, name, description, agent_ids, active, mcp, generated,
                                      resolution_strategy, resolution_threshold)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5, $7, $8)
        RETURNING id
        """,
        name,
        description,
        agent_ids or [],
        not soft,
        mcp,
        id,
        resolution_strategy,
        resolution_threshold,
    )
    await invalidate_tags(["resources", "systems"], redis=redis)
    items = await get_systems(conn, [system_id], redis, bypass_cache=True)
    return items[0]
