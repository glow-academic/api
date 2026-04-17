"""Resolve rubric artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.rubric.get import get_rubrics as get_rubric_artifacts
from app.tools.entries.rubric_drafts.get import get_rubric_drafts
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.points.get import get_points
from app.tools.resources.points.search import search_points
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standard_groups.search import search_standard_groups
from app.tools.resources.standards.get import get_standards
from app.tools.resources.standards.search import search_standards

RUBRIC_FLAG_NAMES = {
    "rubric_active",
    "simulation_rubric",
    "simulation_rubric_flag",
    "video_rubric",
    "video_rubric_flag",
}


@dataclass
class _MergedIds:
    name_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    point_ids: list[UUID]
    standard_group_ids: list[UUID]
    standard_ids: list[UUID]


def _merge_junction_ids(artifact: Any, draft: Any) -> _MergedIds:
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    point_ids = list(artifact.point_ids or []) if artifact else []
    standard_group_ids = list(artifact.standard_group_ids or []) if artifact else []
    standard_ids = list(artifact.standard_ids or []) if artifact else []

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.point_ids:
            point_ids = list(draft.point_ids)
        if draft.standard_group_ids:
            standard_group_ids = list(draft.standard_group_ids)
        if draft.standard_ids:
            standard_ids = list(draft.standard_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        point_ids=point_ids,
        standard_group_ids=standard_group_ids,
        standard_ids=standard_ids,
    )


def _is_rubric_flag(item: Any) -> bool:
    flag_name = getattr(item, "name", None)
    flag_type = getattr(item, "type", None)
    return flag_name in RUBRIC_FLAG_NAMES or flag_type in RUBRIC_FLAG_NAMES


async def resolve_rubric_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    rubric_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    points_search: str | None = None,
    standard_groups_search: str | None = None,
    standards_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    points_limit: int | None = None,
    standard_groups_limit: int | None = None,
    standards_limit: int | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a rubric artifact into fully hydrated resource pairs."""

    user_dept_ids = user_department_ids or []

    async def _fetch_artifact() -> list[Any]:
        if not rubric_id:
            return []
        async with pool.acquire() as conn:
            return await get_rubric_artifacts(
                conn,
                [rubric_id],
                active=None,
                names=True,
                descriptions=True,
                departments=True,
                flags=True,
                points=True,
                standard_groups=True,
                standards=True,
            )

    async def _fetch_draft() -> list[Any]:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_rubric_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())
    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None

    merged = _merge_junction_ids(artifact, draft)

    async def _get_names_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_names(conn, merged.name_ids, redis, bypass_cache)

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
                rubric=True,
            )

    async def _get_descriptions_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, merged.description_ids, redis, bypass_cache)

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
                rubric=True,
            )

    async def _get_flags_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_flags(conn, merged.flag_ids, redis, bypass_cache)

    async def _search_flags_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=flags_search,
                limit_count=flags_limit or 50,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
                rubric=True,
            )

    async def _get_departments_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_departments(conn, merged.department_ids, redis, bypass_cache)

    async def _search_departments_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=departments_search,
                limit_count=departments_limit or 20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all" if rubric_id is None else "recent",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_points_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_points(conn, merged.point_ids, redis, bypass_cache)

    async def _search_points_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_points(
                conn,
                redis,
                search=points_search,
                limit_count=points_limit or 20,
                offset_count=0,
                exclude_ids=merged.point_ids,
                bypass_cache=bypass_cache,
                rubric=True,
            )

    async def _get_standard_groups_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_standard_groups(conn, merged.standard_group_ids, redis, bypass_cache)

    async def _search_standard_groups_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_standard_groups(
                conn,
                redis,
                search=standard_groups_search,
                limit_count=standard_groups_limit or 20,
                offset_count=0,
                exclude_ids=merged.standard_group_ids,
                bypass_cache=bypass_cache,
                rubric=True,
            )

    async def _get_standards_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_standards(conn, merged.standard_ids, redis, bypass_cache)

    async def _search_standards_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_standards(
                conn,
                redis,
                search=standards_search,
                limit_count=standards_limit or 20,
                offset_count=0,
                draft_id=group_id,
                suggest_source="all" if rubric_id is None else "recent",
                exclude_ids=merged.standard_ids,
                standard_group_ids=merged.standard_group_ids or None,
                bypass_cache=bypass_cache,
                rubric=True,
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
        points_selected,
        points_suggestions,
        standard_groups_selected,
        standard_groups_suggestions,
        standards_selected,
        standards_suggestions,
    ) = await asyncio.gather(
        _get_names_selected(),
        _search_names_suggestions(),
        _get_descriptions_selected(),
        _search_descriptions_suggestions(),
        _get_flags_selected(),
        _search_flags_suggestions(),
        _get_departments_selected(),
        _search_departments_suggestions(),
        _get_points_selected(),
        _search_points_suggestions(),
        _get_standard_groups_selected(),
        _search_standard_groups_suggestions(),
        _get_standards_selected(),
        _search_standards_suggestions(),
    )

    filtered_flags_selected = [item for item in flags_selected if _is_rubric_flag(item)]
    filtered_flags_suggestions = [item for item in flags_suggestions if _is_rubric_flag(item)]

    pending_ids: set[UUID] = set()
    if draft:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(draft.pending_point_ids or [])
        pending_ids.update(draft.pending_standard_group_ids or [])
        pending_ids.update(draft.pending_standard_ids or [])

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=artifact.active if artifact else True,
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
            "points": ResourcePair(selected=points_selected, suggestions=points_suggestions),
            "standard_groups": ResourcePair(
                selected=standard_groups_selected,
                suggestions=standard_groups_suggestions,
            ),
            "standards": ResourcePair(
                selected=standards_selected,
                suggestions=standards_suggestions,
            ),
        },
        entries={"pending_ids": pending_ids},
    )
