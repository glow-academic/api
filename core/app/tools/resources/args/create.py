"""Args CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.args.get import get_args
from app.tools.resources.args.types import GetArgResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_arg(
    conn: asyncpg.Connection,
    name: str,
    field_type: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    description: str = "",
    required: bool = False,
    default_value: str = "",
) -> GetArgResponse:
    """Create an arg resource (plain INSERT — no unique constraint)."""
    arg_id = await conn.fetchval(
        """
        INSERT INTO args_resource (id, name, description, field_type, required, default_value, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $7)
        RETURNING id
        """,
        name,
        description,
        field_type,
        required,
        default_value,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "args"], redis=redis)
    items = await get_args(conn, [arg_id], redis, bypass_cache=True)
    return items[0]
