"""Args Outputs CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.args_outputs.get import get_args_outputs
from app.tools.resources.args_outputs.types import GetArgOutputResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_args_output(
    conn: asyncpg.Connection,
    args_id: UUID,
    name: str,
    redis: Redis,
    id: UUID | None = None,
    template: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> GetArgOutputResponse:
    """Create an args_output resource (ON CONFLICT on (args_id, name) upserts)."""
    args_output_id = await conn.fetchval(
        """
        INSERT INTO args_outputs_resource (id, args_id, name, template, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5)
        ON CONFLICT (args_id, name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        args_id,
        name,
        template,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "args_outputs"], redis=redis)
    items = await get_args_outputs(conn, [args_output_id], redis, bypass_cache=True)
    return items[0]
