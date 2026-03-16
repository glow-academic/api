"""Models Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.models.types import GetModelResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_models(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetModelResponse]:
    """Fetch models_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "models"]
    key = cache_key("/v5/resources/models/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetModelResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, value, provider_id,
               department_ids, temperature_level_ids, reasoning_level_ids,
               quality_ids, voice_ids, modality_ids,
               created_at, active, mcp, generated
        FROM models_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetModelResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            value=r["value"],
            provider_id=r["provider_id"],
            department_ids=r["department_ids"] or [],
            temperature_level_ids=r["temperature_level_ids"] or [],
            reasoning_level_ids=r["reasoning_level_ids"] or [],
            quality_ids=r["quality_ids"] or [],
            voice_ids=r["voice_ids"] or [],
            modality_ids=r["modality_ids"] or [],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]

    if not bypass_cache:
        await set_cached(
            key,
            {"items": [i.model_dump(mode="json") for i in items]},
            60,
            tags,
            redis=redis,
        )
    return items
