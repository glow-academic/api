"""Parameters SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.parameters.get import get_parameters
from app.tools.resources.parameters.types import GetParameterResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

# Only 'parameter' follows the standard junction pattern (parameter_parameters_junction).
# document/persona/scenario use non-standard joins through parameter_fields_resource.
JUNCTION_ARTIFACTS = [
    "parameter",
]

DRAFT_ARTIFACTS = [
    "chat",
    "document",
]


async def search_parameters(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    persona_parameter: bool | None = None,
    document_parameter: bool | None = None,
    scenario_parameter: bool | None = None,
    video_parameter: bool | None = None,
    bypass_cache: bool = False,
    *,
    document: bool = False,
    parameter: bool = False,
    persona: bool = False,
    scenario: bool = False,
) -> list[GetParameterResponse]:
    """Search parameters with optional artifact/draft filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "parameter": parameter,
    }

    tags = ["resources", "parameters"]
    key = cache_key(
        "/v5/resources/parameters/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "department_ids": sorted(str(i) for i in (department_ids or [])),
            "field_ids": sorted(str(i) for i in (field_ids or [])),
            "persona_parameter": persona_parameter,
            "document_parameter": document_parameter,
            "scenario_parameter": scenario_parameter,
            "video_parameter": video_parameter,
            "document": document,
            "parameter": parameter,
            "persona": persona,
            "scenario": scenario,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetParameterResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build extra conditions for parameter-specific filters
    extra_conditions: list[tuple[str, object]] = []
    extra_conditions.append(("{alias}.active = ${idx}", True))
    if department_ids:
        extra_conditions.append(
            ("{alias}.department_ids && ${idx}", department_ids),
        )
    if field_ids:
        extra_conditions.append(
            ("{alias}.field_ids && ${idx}", field_ids),
        )
    if persona_parameter is not None:
        extra_conditions.append(
            ("{alias}.persona_parameter = ${idx}", persona_parameter),
        )
    if document_parameter is not None:
        extra_conditions.append(
            ("{alias}.document_parameter = ${idx}", document_parameter),
        )
    if scenario_parameter is not None:
        extra_conditions.append(
            ("{alias}.scenario_parameter = ${idx}", scenario_parameter),
        )
    if video_parameter is not None:
        extra_conditions.append(
            ("{alias}.video_parameter = ${idx}", video_parameter),
        )
    # Non-standard junction filters (go through parameter_fields_resource)
    if document:
        extra_conditions.append(
            (
                "EXISTS (SELECT 1 FROM document_parameter_fields_junction j "
                "JOIN parameter_fields_resource pfr ON pfr.id = j.parameter_fields_id "
                "WHERE pfr.parameter_id = {alias}.id AND j.active = ${idx})",
                True,
            ),
        )
    if persona:
        extra_conditions.append(
            (
                "EXISTS (SELECT 1 FROM persona_parameter_fields_junction j "
                "JOIN parameter_fields_resource pfr ON pfr.id = j.parameter_fields_id "
                "WHERE pfr.parameter_id = {alias}.id AND j.active = ${idx})",
                True,
            ),
        )
    if scenario:
        extra_conditions.append(
            (
                "EXISTS (SELECT 1 FROM scenario_parameter_fields_junction j "
                "JOIN parameter_fields_resource pfr ON pfr.id = j.parameter_fields_id "
                "WHERE pfr.parameter_id = {alias}.id AND j.active = ${idx})",
                True,
            ),
        )

    ids = await search_resource_ids(
        conn,
        table="parameters_resource",
        resource="parameters",
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

    items = await get_parameters(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
