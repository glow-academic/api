"""Tools CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.tools.get import get_tools
from app.tools.resources.tools.types import GetToolResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_tool(
    conn: asyncpg.Connection,
    name: str = "",
    description: str = "",
    redis: Redis = None,
    department_ids: list[UUID] | None = None,
    args_ids: list[UUID] | None = None,
    args_output_ids: list[UUID] | None = None,
    operation: str | None = None,
    artifacts: list[str] | None = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetToolResponse:
    """Create a tool resource (plain INSERT — no unique constraint)."""
    new_tool_id = await conn.fetchval(
        """
        INSERT INTO tools_resource (
            id,
            name,
            description,
            department_ids,
            args_ids,
            args_output_ids,
            operation,
            artifacts,
            active,
            mcp,
            generated
        )
        VALUES (
            COALESCE($10, uuidv7()),
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9,
            $9
        )
        RETURNING id
        """,
        name,
        description,
        department_ids or [],
        args_ids or [],
        args_output_ids or [],
        operation,
        artifacts or [],
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "tools"], redis=redis)
    items = await get_tools(conn, [new_tool_id], redis, bypass_cache=True)
    return items[0]
