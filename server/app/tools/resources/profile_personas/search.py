"""Profile Personas SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.profile_personas.get import get_profile_personas
from app.tools.resources.profile_personas.types import (
    GetProfilePersonaResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["cohort"]

DRAFT_ARTIFACTS = ["cohort"]


async def search_profile_personas(
    conn: asyncpg.Connection,
    redis: Redis,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    cohort: bool = False,
) -> list[GetProfilePersonaResponse]:
    """Search profile personas with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"cohort": cohort}

    extra_conditions: list[tuple[str, object]] = []

    if profile_ids:
        extra_conditions.append(("{alias}.profile_id = ANY(${idx})", profile_ids))
    if persona_ids:
        extra_conditions.append(("{alias}.persona_id = ANY(${idx})", persona_ids))

    tags = ["resources", "profile_personas"]
    key = cache_key(
        "/v5/resources/profile_personas/search",
        {
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "profile_ids": sorted(str(i) for i in (profile_ids or [])),
            "persona_ids": sorted(str(i) for i in (persona_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetProfilePersonaResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="profile_personas_resource",
        resource="profile_personas",
        search_column=None,
        order_column="created_at",
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_profile_personas(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
