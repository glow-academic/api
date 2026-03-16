"""Model Flags CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.model_flags.get import get_model_flags
from app.tools.resources.model_flags.types import GetModelFlagResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_model_flag(
    conn: asyncpg.Connection,
    model_id: UUID,
    flag_id: UUID,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetModelFlagResponse:
    """Create a model_flag resource (plain INSERT — no unique constraint)."""
    model_flag_id = await conn.fetchval(
        """
        INSERT INTO model_flags_resource (id, model_id, flag_id, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        model_id,
        flag_id,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "model_flags"], redis=redis)
    items = await get_model_flags(conn, [model_flag_id], redis, bypass_cache=True)
    return items[0]
