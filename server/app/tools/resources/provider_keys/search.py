"""Provider Keys SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.provider_keys.get import get_provider_keys
from app.tools.resources.provider_keys.types import GetProviderKeyResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["setting"]

DRAFT_ARTIFACTS: list[str] = []


async def search_provider_keys(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    provider_ids: list[UUID] | None = None,
    key_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    setting: bool = False,
) -> list[GetProviderKeyResponse]:
    """Search provider_keys with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "setting": setting,
    }

    tags = ["resources", "provider_keys"]
    key = cache_key(
        "/v5/resources/provider_keys/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "provider_ids": sorted(str(i) for i in (provider_ids or [])),
            "key_ids": sorted(str(i) for i in (key_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetProviderKeyResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build extra conditions for provider_keys-specific filters
    extra_conditions: list[tuple[str, object]] = []
    if provider_ids:
        extra_conditions.append(
            ("{alias}.provider_id = ANY(${idx})", provider_ids),
        )
    if key_ids:
        extra_conditions.append(
            ("{alias}.key_id = ANY(${idx})", key_ids),
        )

    ids = await search_resource_ids(
        conn,
        table="provider_keys_resource",
        resource="provider_keys",
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

    items = await get_provider_keys(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
