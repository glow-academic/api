"""Examples SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.examples.get import get_examples
from app.tools.resources.examples.types import GetExampleResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["persona"]

DRAFT_ARTIFACTS = ["persona"]


async def search_examples(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    persona_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    persona: bool = False,
) -> list[GetExampleResponse]:
    """Search examples with optional artifact/draft filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "persona": persona,
    }

    extra_conditions: list[tuple[str, object]] = []
    if persona_id:
        extra_conditions.append(
            (
                "EXISTS (SELECT 1 FROM persona_examples_junction pe "
                "JOIN personas_resource pr ON pr.id = pe.persona_id "
                "WHERE pe.examples_id = {alias}.id AND pe.active = true "
                "AND (COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 "
                "OR pr.department_ids && ${idx}::uuid[] "
                "OR COALESCE(array_length(pr.department_ids, 1), 0) = 0))",
                department_ids or [],
            )
        )

    tags = ["resources", "examples"]
    key = cache_key(
        "/v5/resources/examples/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "persona_id": str(persona_id) if persona_id else None,
            "department_ids": [str(i) for i in (department_ids or [])],
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetExampleResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="examples_resource",
        resource="examples",
        search_column="example",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        draft_id=draft_id,
        suggest_source=suggest_source,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_examples(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
