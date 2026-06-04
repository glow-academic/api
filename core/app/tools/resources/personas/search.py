"""Personas SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.personas.get import get_personas
from app.tools.resources.personas.types import GetPersonaResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = [
    "cohort_profile",
    "persona",
    "scenario",
]

# cohort_profile_personas_junction's FK to personas_resource is named
# `profile_personas_id`, not the generic `{resource}_id` (`personas_id`).
JUNCTION_COLUMNS = {
    "cohort_profile": "profile_personas_id",
}

DRAFT_ARTIFACTS = [
    "chat",
    "scenario",
]


async def search_personas(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    cohort_profile: bool = False,
    persona: bool = False,
    scenario: bool = False,
) -> list[GetPersonaResponse]:
    """Search personas with optional artifact/draft filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "cohort_profile": cohort_profile,
        "persona": persona,
        "scenario": scenario,
    }

    tags = ["resources", "personas"]
    key = cache_key(
        "/resources/personas/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "department_ids": sorted(str(i) for i in (department_ids or [])),
            "parameter_field_ids": sorted(str(i) for i in (parameter_field_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetPersonaResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build extra conditions for persona-specific filters
    extra_conditions: list[tuple[str, object]] = []
    extra_conditions.append(("{alias}.active = ${idx}", True))
    if department_ids:
        # Personas accessible if they share departments OR have no departments
        extra_conditions.append(
            (
                "({alias}.department_ids && ${idx} OR COALESCE(array_length({alias}.department_ids, 1), 0) = 0)",
                department_ids,
            ),
        )
    if parameter_field_ids:
        # Personas whose parameter_field_ids overlap, or have none (untagged)
        extra_conditions.append(
            (
                "({alias}.parameter_field_ids && ${idx} OR COALESCE(array_length({alias}.parameter_field_ids, 1), 0) = 0)",
                parameter_field_ids,
            ),
        )

    ids = await search_resource_ids(
        conn,
        table="personas_resource",
        resource="personas",
        search_column="name",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        draft_id=draft_id,
        suggest_source=suggest_source,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        junction_columns=JUNCTION_COLUMNS,
        draft_artifacts=DRAFT_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_personas(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
