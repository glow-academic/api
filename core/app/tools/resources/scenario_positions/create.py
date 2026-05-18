"""Scenario Positions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.scenario_positions.get import get_scenario_positions
from app.tools.resources.scenario_positions.types import (
    GetScenarioPositionResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_scenario_position(
    conn: asyncpg.Connection,
    scenario_id: UUID,
    value: int,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetScenarioPositionResponse:
    """Create a scenario_position resource (plain INSERT — no unique constraint)."""
    row_id = await conn.fetchval(
        """
        INSERT INTO scenario_positions_resource (id, scenario_id, value, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        scenario_id,
        value,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "scenario_positions"], redis=redis)
    items = await get_scenario_positions(conn, [row_id], redis, bypass_cache=True)
    return items[0]
