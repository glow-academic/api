"""Scenarios CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.scenarios.types import GetScenarioResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_scenario(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    document_ids: list[UUID] | None = None,
    objective_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    video_ids: list[UUID] | None = None,
    question_ids: list[UUID] | None = None,
    option_ids: list[UUID] | None = None,
    problem_statement_ids: list[UUID] | None = None,
) -> GetScenarioResponse:
    """Create a scenario resource (plain INSERT — no unique constraint)."""
    scenario_id = await conn.fetchval(
        """
        INSERT INTO scenarios_resource (
            id, name, description, active, mcp, generated,
            department_ids, persona_ids, parameter_field_ids, document_ids,
            objective_ids, image_ids, video_ids, question_ids, option_ids,
            problem_statement_ids
        )
        VALUES (
            COALESCE($5, uuidv7()), $1, $2, $3, $4, $4,
            $6, $7, $8, $9,
            $10, $11, $12, $13, $14,
            $15
        )
        RETURNING id
    """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
        persona_ids or [],
        parameter_field_ids or [],
        document_ids or [],
        objective_ids or [],
        image_ids or [],
        video_ids or [],
        question_ids or [],
        option_ids or [],
        problem_statement_ids or [],
    )

    await invalidate_tags(["resources", "scenarios"], redis=redis)
    items = await get_scenarios(conn, [scenario_id], redis, bypass_cache=True)
    return items[0]
