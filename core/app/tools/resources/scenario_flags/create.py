"""Scenario Flags CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.scenario_flags.get import get_scenario_flags
from app.tools.resources.scenario_flags.types import GetScenarioFlagResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_scenario_flag(
    conn: asyncpg.Connection,
    scenario_id: UUID,
    flag_id: UUID,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetScenarioFlagResponse:
    """Create a scenario_flag resource (plain INSERT — no unique constraint)."""
    row_id = await conn.fetchval(
        """
        INSERT INTO scenario_flags_resource (id, scenario_id, flag_id, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        scenario_id,
        flag_id,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "scenario_flags"], redis=redis)
    items = await get_scenario_flags(conn, [row_id], redis, bypass_cache=True)
    return items[0]
