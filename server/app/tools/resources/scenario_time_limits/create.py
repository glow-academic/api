"""Scenario Time Limits CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.scenario_time_limits.get import (
    get_scenario_time_limits,
)
from app.tools.resources.scenario_time_limits.types import (
    GetScenarioTimeLimitResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_scenario_time_limit(
    conn: asyncpg.Connection,
    scenario_id: UUID,
    time_limit_seconds: int,
    redis: Redis,
    id: UUID | None = None,
    negative: bool = False,
    mcp: bool = False,
    soft: bool = False,
) -> GetScenarioTimeLimitResponse:
    """Create a scenario_time_limit resource (plain INSERT — no unique constraint)."""
    row_id = await conn.fetchval(
        """
        INSERT INTO scenario_time_limits_resource
            (id, scenario_id, time_limit_seconds, negative, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5)
        RETURNING id
        """,
        scenario_id,
        time_limit_seconds,
        negative,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "scenario_time_limits"], redis=redis)
    items = await get_scenario_time_limits(conn, [row_id], redis, bypass_cache=True)
    return items[0]
