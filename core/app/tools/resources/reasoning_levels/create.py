"""Reasoning Levels CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.reasoning_levels.get import get_reasoning_levels
from app.tools.resources.reasoning_levels.types import (
    GetReasoningLevelResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_reasoning_level(
    conn: asyncpg.Connection,
    reasoning_level: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetReasoningLevelResponse:
    """Create a reasoning_level resource (plain INSERT, no unique constraint)."""
    level_id = await conn.fetchval(
        """
        INSERT INTO reasoning_levels_resource (id, reasoning_level, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        RETURNING id
        """,
        reasoning_level,
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "reasoning_levels"], redis=redis)
    items = await get_reasoning_levels(conn, [level_id], redis, bypass_cache=True)
    return items[0]
