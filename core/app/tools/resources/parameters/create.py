"""Parameters CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.parameters.get import get_parameters
from app.tools.resources.parameters.types import GetParameterResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_parameter(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    persona_parameter: bool = False,
    document_parameter: bool = False,
    scenario_parameter: bool = False,
    video_parameter: bool = False,
) -> GetParameterResponse:
    """Create a parameter resource (plain INSERT — no unique constraint)."""
    parameter_id = await conn.fetchval(
        """
        INSERT INTO parameters_resource (id, name, description, active, mcp, generated, department_ids, field_ids,
                                         persona_parameter, document_parameter, scenario_parameter, video_parameter)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4, $6, $7, $8, $9, $10, $11)
        RETURNING id
    """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
        field_ids or [],
        persona_parameter,
        document_parameter,
        scenario_parameter,
        video_parameter,
    )

    await invalidate_tags(["resources", "parameters"], redis=redis)
    items = await get_parameters(conn, [parameter_id], redis, bypass_cache=True)
    return items[0]
