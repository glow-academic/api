"""Model Flags SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.model_flags.get import get_model_flags
from app.tools.resources.model_flags.types import GetModelFlagResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["eval"]


async def search_model_flags(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    eval: bool = False,
) -> list[GetModelFlagResponse]:
    """Search model flags with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"eval": eval}

    extra_conditions: list[tuple[str, object]] = []

    # Search by name/description via joined flags_resource
    if search:
        extra_conditions.append(
            (
                "EXISTS (SELECT 1 FROM flags_resource f "
                "WHERE f.id = {alias}.flag_id AND f.active = true "
                "AND (LOWER(f.name) LIKE '%' || LOWER(${idx}) || '%' "
                "OR LOWER(COALESCE(f.description, '')) LIKE '%' || LOWER(${idx}) || '%'))",
                search,
            )
        )

    if model_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.model_id = ANY(${idx}::uuid[]))",
                model_ids,
            )
        )
    if flag_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.flag_id = ANY(${idx}::uuid[]))",
                flag_ids,
            )
        )

    tags = ["resources", "model_flags"]
    key = cache_key(
        "/v5/resources/model_flags/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "model_ids": sorted(str(i) for i in (model_ids or [])),
            "flag_ids": sorted(str(i) for i in (flag_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetModelFlagResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="model_flags_resource",
        resource="model_flags",
        search_column="id::text",
        search=None,  # Search handled via extra_conditions (JOIN on flags_resource)
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        order_column="created_at",
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_model_flags(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
