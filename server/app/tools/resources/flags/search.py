"""Flags SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.types import GetFlagResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = [
    "agent",
    "auth",
    "cohort",
    "department",
    "document",
    "eval",
    "field",
    "model",
    "parameter",
    "persona",
    "profile",
    "provider",
    "rubric",
    "scenario",
    "setting",
    "simulation",
    "tool",
]


async def search_flags(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    flag_type: str | None = None,
    bypass_cache: bool = False,
    *,
    agent: bool = False,
    auth: bool = False,
    cohort: bool = False,
    department: bool = False,
    document: bool = False,
    eval: bool = False,
    field: bool = False,
    model: bool = False,
    parameter: bool = False,
    persona: bool = False,
    profile: bool = False,
    provider: bool = False,
    rubric: bool = False,
    scenario: bool = False,
    setting: bool = False,
    simulation: bool = False,
    tool: bool = False,
) -> list[GetFlagResponse]:
    """Search flags with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "agent": agent,
        "auth": auth,
        "cohort": cohort,
        "department": department,
        "document": document,
        "eval": eval,
        "field": field,
        "model": model,
        "parameter": parameter,
        "persona": persona,
        "profile": profile,
        "provider": provider,
        "rubric": rubric,
        "scenario": scenario,
        "setting": setting,
        "simulation": simulation,
        "tool": tool,
    }

    extra_conditions: list[tuple[str, object]] = []
    if flag_type:
        extra_conditions.append(("{alias}.type = ${idx}::flag_type", flag_type))

    tags = ["resources", "flags"]
    key = cache_key(
        "/v5/resources/flags/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "flag_type": flag_type,
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetFlagResponse.model_validate(item) for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="flags_resource",
        resource="flags",
        search_column="name",
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

    items = await get_flags(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
