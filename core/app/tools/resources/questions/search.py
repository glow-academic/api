"""Questions SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.questions.get import get_questions
from app.tools.resources.questions.types import GetQuestionResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["scenario"]


async def search_questions(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    allow_multiple: bool | None = None,
    bypass_cache: bool = False,
    *,
    scenario: bool = False,
) -> list[GetQuestionResponse]:
    """Search questions with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"scenario": scenario}

    extra_conditions: list[tuple[str, object]] = []
    if allow_multiple is not None:
        extra_conditions.append(
            ("{alias}.allow_multiple = ${idx}::boolean", allow_multiple)
        )

    tags = ["resources", "questions"]
    key = cache_key(
        "/v5/resources/questions/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "allow_multiple": allow_multiple,
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetQuestionResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="questions_resource",
        resource="questions",
        search_column="question_text",
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

    items = await get_questions(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
