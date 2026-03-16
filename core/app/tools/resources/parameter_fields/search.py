"""Parameter Fields SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.parameter_fields.types import (
    GetParameterFieldResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["document", "persona", "scenario"]

DRAFT_ARTIFACTS = ["document", "persona", "scenario"]


async def search_parameter_fields(
    conn: asyncpg.Connection,
    redis: Redis,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    conditional_parameter_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    document: bool = False,
    persona: bool = False,
    scenario: bool = False,
) -> list[GetParameterFieldResponse]:
    """Search parameter fields with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "document": document,
        "persona": persona,
        "scenario": scenario,
    }

    extra_conditions: list[tuple[str, object]] = []

    if parameter_ids:
        extra_conditions.append(("{alias}.parameter_id = ANY(${idx})", parameter_ids))
    if field_ids:
        extra_conditions.append(("{alias}.field_id = ANY(${idx})", field_ids))
    if conditional_parameter_ids:
        extra_conditions.append(
            (
                "EXISTS (SELECT 1 FROM conditional_parameters_resource cpr "
                "JOIN fields_resource fr ON cpr.id = ANY(fr.conditional_parameter_ids) "
                "WHERE fr.id = {alias}.field_id AND cpr.active = true "
                "AND cpr.parameter_id = ANY(${idx}))",
                conditional_parameter_ids,
            )
        )

    tags = ["resources", "parameter_fields"]
    key = cache_key(
        "/v5/resources/parameter_fields/search",
        {
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "parameter_ids": sorted(str(i) for i in (parameter_ids or [])),
            "field_ids": sorted(str(i) for i in (field_ids or [])),
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
                GetParameterFieldResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="parameter_fields_resource",
        resource="parameter_fields",
        search_column=None,
        order_column="created_at",
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_parameter_fields(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
