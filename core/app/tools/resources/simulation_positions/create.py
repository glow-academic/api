"""Simulation Positions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.simulation_positions.get import (
    get_simulation_positions,
)
from app.tools.resources.simulation_positions.types import (
    GetSimulationPositionResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_simulation_position(
    conn: asyncpg.Connection,
    simulation_id: UUID,
    value: int,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetSimulationPositionResponse:
    """Create a simulation_position resource (plain INSERT — no unique constraint)."""
    row_id = await conn.fetchval(
        """
        INSERT INTO simulation_positions_resource (id, simulation_id, value, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        simulation_id,
        value,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "simulation_positions"], redis=redis)
    items = await get_simulation_positions(conn, [row_id], redis, bypass_cache=True)
    return items[0]
