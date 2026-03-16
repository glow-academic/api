"""Model Positions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.model_positions.get import get_model_positions
from app.tools.resources.model_positions.types import GetModelPositionResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_model_position(
    conn: asyncpg.Connection,
    model_id: UUID,
    value: int,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetModelPositionResponse:
    """Create a model_position resource (plain INSERT — no unique constraint)."""
    model_position_id = await conn.fetchval(
        """
        INSERT INTO model_positions_resource (id, model_id, value, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        model_id,
        value,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "model_positions"], redis=redis)
    items = await get_model_positions(
        conn, [model_position_id], redis, bypass_cache=True
    )
    return items[0]
