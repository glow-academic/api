"""Simulation Availability CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.simulation_availability.get import (
    get_simulation_availability,
)
from app.tools.resources.simulation_availability.types import (
    GetSimulationAvailabilityResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_simulation_availability(
    conn: asyncpg.Connection,
    simulation_id: UUID,
    time: datetime,
    availability_type: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetSimulationAvailabilityResponse:
    """Create a simulation_availability resource (ON CONFLICT on (simulation_id, type))."""
    row_id = await conn.fetchval(
        """
        INSERT INTO simulation_availability_resource
            (id, simulation_id, time, type, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3::availability_type, $4, $5, $5)
        ON CONFLICT (simulation_id, type) DO UPDATE SET time = EXCLUDED.time
        RETURNING id
        """,
        simulation_id,
        time,
        availability_type,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "simulation_availability"], redis=redis)
    items = await get_simulation_availability(conn, [row_id], redis, bypass_cache=True)
    return items[0]
