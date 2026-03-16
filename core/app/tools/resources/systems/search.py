"""Systems SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.systems.get import get_systems
from app.tools.resources.systems.types import GetSystemResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["setting"]

DRAFT_ARTIFACTS: list[str] = []


async def search_systems(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    agent_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    setting: bool = False,
) -> list[GetSystemResponse]:
    """Search systems with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "setting": setting,
    }

    tags = ["resources", "systems"]
    key = cache_key(
        "/v5/resources/systems/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "agent_ids": sorted(str(i) for i in (agent_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetSystemResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build extra conditions for systems-specific filters
    extra_conditions: list[tuple[str, object]] = []
    if agent_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.agent_ids && ${idx}::uuid[])",
                agent_ids,
            ),
        )

    ids = await search_resource_ids(
        conn,
        table="systems_resource",
        resource="systems",
        search_column="name",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        draft_id=draft_id,
        suggest_source=suggest_source,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS if DRAFT_ARTIFACTS else None,
        additional_search_columns=["description"],
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_systems(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
