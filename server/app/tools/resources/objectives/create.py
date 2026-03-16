"""Objectives CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.objectives.get import get_objectives
from app.tools.resources.objectives.types import GetObjectiveResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_objective(
    conn: asyncpg.Connection,
    objective: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetObjectiveResponse:
    """Create an objective resource."""
    objective_id = await conn.fetchval(
        """
        INSERT INTO objectives_resource (id, objective, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        RETURNING id
    """,
        objective,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "objectives"], redis=redis)
    items = await get_objectives(conn, [objective_id], redis, bypass_cache=True)
    return items[0]
