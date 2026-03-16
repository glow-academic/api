"""Instructions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.instructions.types import GetInstructionResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_instruction(
    conn: asyncpg.Connection,
    template: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetInstructionResponse:
    """Create an instruction resource."""
    instruction_id = await conn.fetchval(
        """
        INSERT INTO instructions_resource (id, template, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        RETURNING id
    """,
        template,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "instructions"], redis=redis)
    items = await get_instructions(conn, [instruction_id], redis, bypass_cache=True)
    return items[0]
