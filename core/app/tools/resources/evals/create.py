"""Evals CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.evals.get import get_evals
from app.tools.resources.evals.types import GetEvalResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_eval(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    model_rubric_ids: list[UUID] | None = None,
    model_flag_ids: list[UUID] | None = None,
    model_position_ids: list[UUID] | None = None,
) -> GetEvalResponse:
    """Create an eval resource (plain INSERT — no unique constraint)."""
    eval_id = await conn.fetchval(
        """
        INSERT INTO evals_resource (
            id, name, description, active, mcp, generated,
            department_ids, model_ids, model_rubric_ids, model_flag_ids, model_position_ids
        )
        VALUES (
            COALESCE($5, uuidv7()), $1, $2, $3, $4, $4,
            $6, $7, $8, $9, $10
        )
        RETURNING id
    """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
        model_ids or [],
        model_rubric_ids or [],
        model_flag_ids or [],
        model_position_ids or [],
    )

    await invalidate_tags(["resources", "evals"], redis=redis)
    items = await get_evals(conn, [eval_id], redis, bypass_cache=True)
    return items[0]
