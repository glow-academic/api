"""Modalities CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.modalities.get import get_modalities
from app.tools.resources.modalities.types import GetModalityResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_modality(
    conn: asyncpg.Connection,
    modality: str,
    redis: Redis,
    id: UUID | None = None,
    is_input: bool = False,
    mcp: bool = False,
    soft: bool = False,
) -> GetModalityResponse:
    """Create a modality resource (plain INSERT, no unique constraint)."""
    modality_id = await conn.fetchval(
        """
        INSERT INTO modalities_resource (id, modality, is_input, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        modality,
        is_input,
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "modalities"], redis=redis)
    items = await get_modalities(conn, [modality_id], redis, bypass_cache=True)
    return items[0]
