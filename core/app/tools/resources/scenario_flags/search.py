"""Scenario Flags SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.scenario_flags.get import get_scenario_flags
from app.tools.resources.scenario_flags.types import GetScenarioFlagResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["simulation"]


async def search_scenario_flags(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    simulation: bool = False,
) -> list[GetScenarioFlagResponse]:
    """Search scenario flags with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"simulation": simulation}

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

    if scenario_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.scenario_id = ANY(${idx}::uuid[]))",
                scenario_ids,
            )
        )
    if flag_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.flag_id = ANY(${idx}::uuid[]))",
                flag_ids,
            )
        )

    tags = ["resources", "scenario_flags"]
    key = cache_key(
        "/v5/resources/scenario_flags/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "scenario_ids": sorted(str(i) for i in (scenario_ids or [])),
            "flag_ids": sorted(str(i) for i in (flag_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetScenarioFlagResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="scenario_flags_resource",
        resource="scenario_flags",
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

    items = await get_scenario_flags(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
