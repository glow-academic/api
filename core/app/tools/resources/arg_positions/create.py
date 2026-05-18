"""Arg Positions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.arg_positions.get import get_arg_positions
from app.tools.resources.arg_positions.types import GetArgPositionResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_arg_position(
    conn: asyncpg.Connection,
    args_id: UUID,
    value: int,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetArgPositionResponse:
    """Create an arg_position resource (plain INSERT — no unique constraint)."""
    arg_position_id = await conn.fetchval(
        """
        INSERT INTO arg_positions_resource (id, args_id, value, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        args_id,
        value,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "arg_positions"], redis=redis)
    items = await get_arg_positions(conn, [arg_position_id], redis, bypass_cache=True)
    return items[0]
