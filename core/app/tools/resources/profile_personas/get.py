"""Profile Personas Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.profile_personas.types import (
    GetProfilePersonaResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_profile_personas(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetProfilePersonaResponse]:
    """Fetch profile_personas_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "profile_personas"]
    key = cache_key(
        "/v5/resources/profile_personas/get", {"ids": [str(id) for id in ids]}
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetProfilePersonaResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, profile_id, persona_id,
               created_at, active, generated, mcp
        FROM profile_personas_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetProfilePersonaResponse(
            id=r["id"],
            profile_id=r["profile_id"],
            persona_id=r["persona_id"],
            created_at=r["created_at"],
            active=r["active"],
            generated=r["generated"],
            mcp=r["mcp"],
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
