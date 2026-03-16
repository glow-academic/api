"""Fields SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.fields.get import get_fields
from app.tools.resources.fields.types import GetFieldResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = [
    "field",
    "parameter",
]

DRAFT_ARTIFACTS = [
    "chat",
    "parameter",
]


async def search_fields(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    conditional_parameter_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    field: bool = False,
    parameter: bool = False,
) -> list[GetFieldResponse]:
    """Search fields with optional artifact/draft filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "field": field,
        "parameter": parameter,
    }

    tags = ["resources", "fields"]
    key = cache_key(
        "/v5/resources/fields/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "department_ids": [str(i) for i in (department_ids or [])],
            "conditional_parameter_ids": sorted(
                str(i) for i in (conditional_parameter_ids or [])
            ),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetFieldResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build extra conditions for field-specific filters
    extra_conditions: list[tuple[str, object]] = []
    if department_ids:
        extra_conditions.append(
            (
                "({alias}.department_ids && ${idx} OR COALESCE(array_length({alias}.department_ids, 1), 0) = 0)",
                department_ids,
            ),
        )
    if conditional_parameter_ids:
        extra_conditions.append(
            ("{alias}.conditional_parameter_ids && ${idx}", conditional_parameter_ids),
        )

    ids = await search_resource_ids(
        conn,
        table="fields_resource",
        resource="fields",
        search_column="name",
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

    items = await get_fields(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
