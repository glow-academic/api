"""Descriptions SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.types import GetDescriptionResponse
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
    "provider",
    "rubric",
    "scenario",
    "setting",
    "simulation",
    "tool",
]

DRAFT_ARTIFACTS = [
    "agent",
    "auth",
    "chat",
    "cohort",
    "department",
    "document",
    "eval",
    "field",
    "invocation",
    "model",
    "parameter",
    "persona",
    "provider",
    "rubric",
    "scenario",
    "setting",
    "simulation",
    "tool",
]


async def search_descriptions(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
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
    provider: bool = False,
    rubric: bool = False,
    scenario: bool = False,
    setting: bool = False,
    simulation: bool = False,
    tool: bool = False,
) -> list[GetDescriptionResponse]:
    """Search descriptions with optional artifact/draft filters."""
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
        "provider": provider,
        "rubric": rubric,
        "scenario": scenario,
        "setting": setting,
        "simulation": simulation,
        "tool": tool,
    }

    tags = ["resources", "descriptions"]
    key = cache_key(
        "/v5/resources/descriptions/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
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
                GetDescriptionResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="descriptions_resource",
        resource="descriptions",
        search_column="description",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        draft_id=draft_id,
        suggest_source=suggest_source,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_descriptions(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
