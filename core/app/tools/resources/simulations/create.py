"""Simulations CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.simulations.get import get_simulations
from app.tools.resources.simulations.types import GetSimulationResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_simulation(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    scenario_rubric_ids: list[UUID] | None = None,
    scenario_time_limit_ids: list[UUID] | None = None,
    scenario_position_ids: list[UUID] | None = None,
    scenario_flag_ids: list[UUID] | None = None,
) -> GetSimulationResponse:
    """Create a simulation resource (plain INSERT — no unique constraint)."""
    simulation_id = await conn.fetchval(
        """
        INSERT INTO simulations_resource (id, name, description, active, mcp, generated,
            department_ids, scenario_ids, scenario_rubric_ids,
            scenario_time_limit_ids, scenario_position_ids, scenario_flag_ids)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4,
            $6, $7, $8, $9, $10, $11)
        RETURNING id
    """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
        scenario_ids or [],
        scenario_rubric_ids or [],
        scenario_time_limit_ids or [],
        scenario_position_ids or [],
        scenario_flag_ids or [],
    )

    await invalidate_tags(["resources", "simulations"], redis=redis)
    items = await get_simulations(conn, [simulation_id], redis, bypass_cache=True)
    return items[0]
