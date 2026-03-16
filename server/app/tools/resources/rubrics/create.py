"""Rubrics CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.rubrics.types import GetRubricResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_rubric(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    standard_group_ids: list[UUID] | None = None,
) -> GetRubricResponse:
    """Create a rubric resource (plain INSERT — no unique constraint)."""
    rubric_id = await conn.fetchval(
        """
        INSERT INTO rubrics_resource (id, name, description, active, mcp, generated, department_ids, standard_group_ids)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4, $6, $7)
        RETURNING id
    """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
        standard_group_ids or [],
    )

    await invalidate_tags(["resources", "rubrics"], redis=redis)
    items = await get_rubrics(conn, [rubric_id], redis, bypass_cache=True)
    return items[0]
