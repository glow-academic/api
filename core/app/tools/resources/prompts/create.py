"""Prompts CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.prompts.get import get_prompts
from app.tools.resources.prompts.types import GetPromptResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_prompt(
    conn: asyncpg.Connection,
    system_prompt: str,
    name: str,
    description: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetPromptResponse:
    """Create a prompt resource."""
    prompt_id = await conn.fetchval(
        """
        INSERT INTO prompts_resource (id, system_prompt, name, description, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5)
        RETURNING id
    """,
        system_prompt,
        name,
        description,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "prompts"], redis=redis)
    items = await get_prompts(conn, [prompt_id], redis, bypass_cache=True)
    return items[0]
