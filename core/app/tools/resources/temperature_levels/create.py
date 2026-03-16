"""Temperature Levels CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.temperature_levels.types import (
    GetTemperatureLevelResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_temperature_level(
    conn: asyncpg.Connection,
    temperature: float,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetTemperatureLevelResponse:
    """Create a temperature_level resource (plain INSERT, no unique constraint)."""
    level_id = await conn.fetchval(
        """
        INSERT INTO temperature_levels_resource (id, temperature, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        RETURNING id
        """,
        temperature,
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "temperature_levels"], redis=redis)
    items = await get_temperature_levels(conn, [level_id], redis, bypass_cache=True)
    return items[0]
