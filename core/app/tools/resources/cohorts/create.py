"""Cohorts CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.cohorts.get import get_cohorts
from app.tools.resources.cohorts.types import GetCohortResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_cohort(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    profile_persona_ids: list[UUID] | None = None,
    simulation_position_ids: list[UUID] | None = None,
    simulation_availability_ids: list[UUID] | None = None,
) -> GetCohortResponse:
    """Create a cohort resource (plain INSERT — no unique constraint)."""
    cohort_id = await conn.fetchval(
        """
        INSERT INTO cohorts_resource (
            id, name, description, active, mcp, generated,
            department_ids, simulation_ids, profile_ids,
            profile_persona_ids, simulation_position_ids, simulation_availability_ids
        )
        VALUES (
            COALESCE($5, uuidv7()), $1, $2, $3, $4, $4,
            $6, $7, $8, $9, $10, $11
        )
        RETURNING id
    """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
        simulation_ids or [],
        profile_ids or [],
        profile_persona_ids or [],
        simulation_position_ids or [],
        simulation_availability_ids or [],
    )

    await invalidate_tags(["resources", "cohorts"], redis=redis)
    items = await get_cohorts(conn, [cohort_id], redis, bypass_cache=True)
    return items[0]
