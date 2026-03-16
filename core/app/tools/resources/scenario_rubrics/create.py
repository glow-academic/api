"""Scenario Rubrics CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.scenario_rubrics.get import get_scenario_rubrics
from app.tools.resources.scenario_rubrics.types import (
    GetScenarioRubricResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_scenario_rubric(
    conn: asyncpg.Connection,
    scenario_id: UUID,
    rubric_id: UUID,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetScenarioRubricResponse:
    """Create a scenario_rubric resource (plain INSERT — no unique constraint)."""
    row_id = await conn.fetchval(
        """
        INSERT INTO scenario_rubrics_resource (id, scenario_id, rubric_id, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        scenario_id,
        rubric_id,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "scenario_rubrics"], redis=redis)
    items = await get_scenario_rubrics(conn, [row_id], redis, bypass_cache=True)
    return items[0]
