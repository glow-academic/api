"""Agents SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.agents.get import get_agents
from app.tools.resources.agents.types import GetAgentResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["agent", "setting"]


async def search_agents(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    instruction_ids: list[UUID] | None = None,
    model_ids: list[UUID] | None = None,
    prompt_ids: list[UUID] | None = None,
    quality: str | None = None,
    bypass_cache: bool = False,
    *,
    agent: bool = False,
    setting: bool = False,
) -> list[GetAgentResponse]:
    """Search agents with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"agent": agent, "setting": setting}

    extra_conditions: list[tuple[str, object]] = []
    if department_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.department_ids && ${idx}::uuid[])",
                department_ids,
            )
        )
    if tool_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.tool_ids && ${idx}::uuid[])",
                tool_ids,
            )
        )
    if instruction_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.instruction_ids && ${idx}::uuid[])",
                instruction_ids,
            )
        )
    if model_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.model_id = ANY(${idx}::uuid[]))",
                model_ids,
            )
        )
    if prompt_ids:
        extra_conditions.append(
            (
                "(COALESCE(array_length(${idx}::uuid[], 1), 0) = 0 OR {alias}.prompt_id = ANY(${idx}::uuid[]))",
                prompt_ids,
            )
        )
    if quality is not None:
        extra_conditions.append(("{alias}.quality::text = ${idx}", quality))

    tags = ["resources", "agents"]
    key = cache_key(
        "/v5/resources/agents/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "department_ids": sorted(str(i) for i in (department_ids or [])),
            "tool_ids": sorted(str(i) for i in (tool_ids or [])),
            "instruction_ids": sorted(str(i) for i in (instruction_ids or [])),
            "model_ids": sorted(str(i) for i in (model_ids or [])),
            "prompt_ids": sorted(str(i) for i in (prompt_ids or [])),
            "quality": quality,
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetAgentResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="agents_resource",
        resource="agents",
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

    items = await get_agents(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
