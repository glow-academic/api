"""Model Rubrics CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.model_rubrics.get import get_model_rubrics
from app.tools.resources.model_rubrics.types import GetModelRubricResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_model_rubric(
    conn: asyncpg.Connection,
    model_id: UUID,
    rubric_id: UUID,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetModelRubricResponse:
    """Create a model_rubric resource (plain INSERT — no unique constraint)."""
    model_rubric_id = await conn.fetchval(
        """
        INSERT INTO model_rubrics_resource (id, model_id, rubric_id, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        model_id,
        rubric_id,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "model_rubrics"], redis=redis)
    items = await get_model_rubrics(conn, [model_rubric_id], redis, bypass_cache=True)
    return items[0]
