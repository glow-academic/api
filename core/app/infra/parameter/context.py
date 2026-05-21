"""Resolve parameter artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.parameter.get import get_parameters as get_parameter_artifacts
from app.tools.entries.parameter_drafts.get import get_parameter_drafts
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.fields.get import get_fields
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.parameter_fields.search import search_parameter_fields

PARAMETER_FLAG_NAMES = {
    "parameter_active",
    "parameter_simulation",
    "parameter_document",
    "parameter_persona",
    "parameter_scenario",
    "parameter_video",
}


@dataclass
class _MergedIds:
    name_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    field_ids: list[UUID]


def _merge_junction_ids(artifact: Any, draft: Any) -> _MergedIds:
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    field_ids = list(artifact.field_ids or []) if artifact else []

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.field_ids:
            field_ids = list(draft.field_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        field_ids=field_ids,
    )


async def resolve_parameter_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    parameter_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    parameter_field_parameter_ids: list[UUID] | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    parameter_fields_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    parameter_fields_limit: int | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a parameter artifact into fully hydrated resource pairs."""

    user_dept_ids = user_department_ids or []
    parameter_ids = parameter_field_parameter_ids or []

    async def _fetch_artifact() -> list[Any]:
        if not parameter_id:
            return []
        async with pool.acquire() as conn:
            return await get_parameter_artifacts(
                conn,
                [parameter_id],
                active=None,
                names=True,
                descriptions=True,
                departments=True,
                flags=True,
                fields=True,
            )

    async def _fetch_draft() -> list[Any]:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_parameter_drafts(conn, [draft_id], redis)

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())
    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None

    merged = _merge_junction_ids(artifact, draft)
    active = artifact.active if artifact else True

    async def _get_names_selected() -> list[Any]:
        return await get_names(pool, merged.name_ids, redis, bypass_cache)

    async def _search_names_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                search=names_search,
                limit_count=names_limit or 20,
                draft_id=group_id,
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                parameter=True,
            )

    async def _get_descriptions_selected() -> list[Any]:
        return await get_descriptions(pool, merged.description_ids, redis, bypass_cache
        )

    async def _search_descriptions_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=descriptions_search,
                limit_count=descriptions_limit or 20,
                draft_id=group_id,
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                parameter=True,
            )

    async def _get_flags_selected() -> list[Any]:
        return await get_flags(pool, merged.flag_ids, redis, bypass_cache)

    async def _search_flags_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            # Don't filter on parameter_flags_junction — new parameters
            # have no junction rows. PARAMETER_FLAG_NAMES post-filter
            # narrows to relevant types downstream.
            return await search_flags(
                conn,
                redis,
                search=flags_search,
                limit_count=flags_limit or 200,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_departments_selected() -> list[Any]:
        return await get_departments(
            pool, merged.department_ids, redis, bypass_cache
        )

    async def _search_departments_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=departments_search,
                limit_count=departments_limit or 20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all" if parameter_id is None else "recent",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_parameter_fields_selected() -> list[Any]:
        return await get_parameter_fields(pool, merged.field_ids, redis, bypass_cache
        )

    async def _search_parameter_fields_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_parameter_fields(
                conn,
                redis,
                limit_count=parameter_fields_limit or 20,
                exclude_ids=merged.field_ids,
                parameter_ids=parameter_ids or None,
                bypass_cache=bypass_cache,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        flags_selected,
        flags_suggestions,
        departments_selected,
        departments_suggestions,
        parameter_fields_selected,
        parameter_fields_suggestions,
    ) = await asyncio.gather(
        _get_names_selected(),
        _search_names_suggestions(),
        _get_descriptions_selected(),
        _search_descriptions_suggestions(),
        _get_flags_selected(),
        _search_flags_suggestions(),
        _get_departments_selected(),
        _search_departments_suggestions(),
        _get_parameter_fields_selected(),
        _search_parameter_fields_suggestions(),
    )

    all_parameter_fields = [
        *parameter_fields_selected,
        *parameter_fields_suggestions,
    ]
    field_ids = sorted(
        {
            item.field_id
            for item in all_parameter_fields
            if getattr(item, "field_id", None) is not None
        },
        key=str,
    )
    if field_ids:
        fields = await get_fields(pool, field_ids, redis, bypass_cache)
    else:
        fields = []

    field_map = {field.id: field for field in fields if getattr(field, "id", None)}

    filtered_flags_selected = [
        item for item in flags_selected if getattr(item, "name", None) in PARAMETER_FLAG_NAMES
    ]
    filtered_flags_suggestions = [
        item
        for item in flags_suggestions
        if getattr(item, "name", None) in PARAMETER_FLAG_NAMES
    ]

    pending_ids: set[UUID] = set()
    if draft:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(draft.pending_field_ids or [])

    # Hydrate SVG icons onto each flag (icon_id → icon markup).
    async with pool.acquire() as conn:
        await hydrate_flag_icons(
            list(filtered_flags_selected) + list(filtered_flags_suggestions,), conn, redis, bypass_cache
        )

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=active,
        group_id=group_id,
        resources={
            "names": ResourcePair(selected=names_selected, suggestions=names_suggestions),
            "descriptions": ResourcePair(
                selected=descriptions_selected,
                suggestions=descriptions_suggestions,
            ),
            "flags": ResourcePair(
                selected=filtered_flags_selected,
                suggestions=filtered_flags_suggestions,
            ),
            "departments": ResourcePair(
                selected=departments_selected,
                suggestions=departments_suggestions,
            ),
            "parameter_fields": ResourcePair(
                selected=parameter_fields_selected,
                suggestions=parameter_fields_suggestions,
            ),
        },
        entries={
            "draft_name": draft.name if draft else None,
            "fields": fields,
            "field_map": field_map,
            "pending_ids": pending_ids,
            "parameter_fields_search": parameter_fields_search,
        },
    )
