"""Settings SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.settings.get import get_settings
from app.tools.resources.settings.types import GetSettingResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["department", "setting"]


async def search_settings(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    agent_ids: list[UUID] | None = None,
    provider_key_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    department: bool = False,
    setting: bool = False,
) -> list[GetSettingResponse]:
    """Search settings with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"department": department, "setting": setting}

    extra_conditions: list[tuple[str, object]] = []
    if department_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.department_ids && ${idx}::uuid[])",
                department_ids,
            )
        )
    if agent_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR EXISTS ("
                "SELECT 1 FROM setting_systems_junction ssj "
                "JOIN systems_resource sr ON sr.id = ssj.systems_id "
                "WHERE ssj.setting_id = {alias}.id AND ssj.active = true AND sr.active = true "
                "AND sr.agent_ids && ${idx}::uuid[]))",
                agent_ids,
            )
        )
    if provider_key_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.provider_key_ids && ${idx}::uuid[])",
                provider_key_ids,
            )
        )
    if auth_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.auth_ids && ${idx}::uuid[])",
                auth_ids,
            )
        )

    tags = ["resources", "settings"]
    key = cache_key(
        "/v5/resources/settings/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "department_ids": sorted(str(i) for i in (department_ids or [])),
            "agent_ids": sorted(str(i) for i in (agent_ids or [])),
            "provider_key_ids": sorted(str(i) for i in (provider_key_ids or [])),
            "auth_ids": sorted(str(i) for i in (auth_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetSettingResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="settings_resource",
        resource="settings",
        search_column="name",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        additional_search_columns=["description"],
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_settings(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
