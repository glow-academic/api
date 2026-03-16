"""Models CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.models.get import get_models
from app.tools.resources.models.types import GetModelResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_model(
    conn: asyncpg.Connection,
    value: str,
    name: str = "",
    description: str = "",
    redis: Redis = None,
    department_ids: list[UUID] | None = None,
    provider_id: UUID | None = None,
    temperature_level_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    modality_ids: list[UUID] | None = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetModelResponse:
    """Create a model resource (plain INSERT — no unique constraint)."""
    model_id = await conn.fetchval(
        """
        INSERT INTO models_resource (
            id,
            value,
            name,
            description,
            department_ids,
            provider_id,
            temperature_level_ids,
            reasoning_level_ids,
            quality_ids,
            voice_ids,
            modality_ids,
            active,
            mcp,
            generated
        )
        VALUES (
            COALESCE($13, uuidv7()),
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9,
            $10,
            $11,
            $12,
            $12
        )
        RETURNING id
        """,
        value,
        name,
        description,
        department_ids or [],
        provider_id,
        temperature_level_ids or [],
        reasoning_level_ids or [],
        quality_ids or [],
        voice_ids or [],
        modality_ids or [],
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "models"], redis=redis)
    items = await get_models(conn, [model_id], redis, bypass_cache=True)
    return items[0]
