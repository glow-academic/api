"""Options SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.options.get import get_options
from app.tools.resources.options.types import GetOptionResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["scenario"]


async def search_options(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    question_ids: list[UUID] | None = None,
    is_correct: bool | None = None,
    bypass_cache: bool = False,
    *,
    scenario: bool = False,
) -> list[GetOptionResponse]:
    """Search options with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"scenario": scenario}

    extra_conditions: list[tuple[str, object]] = []
    if question_ids:
        extra_conditions.append(("{alias}.question_id = ANY(${idx})", question_ids))
    if is_correct is not None:
        extra_conditions.append(("{alias}.is_correct = ${idx}::boolean", is_correct))

    tags = ["resources", "options"]
    key = cache_key(
        "/v5/resources/options/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "question_ids": sorted(str(i) for i in (question_ids or [])),
            "is_correct": is_correct,
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetOptionResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="options_resource",
        resource="options",
        search_column="option_text",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_options(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
