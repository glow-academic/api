"""Resolve rubric artifact context — merged junctions + hydrated resources.

Given a rubric_id (and optional draft_id), fetches the published artifact
and draft entry, merges junction IDs (draft overrides published), then
hydrates all resources in parallel (selected + suggestions).

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Artifact + draft fetchers
from app.tools.artifacts.rubric.get import (
    get_rubrics as get_rubric_artifacts,
)
from app.tools.entries.rubric_drafts.get import get_rubric_drafts

# Resource get fetchers (by known IDs)
from app.tools.resources.departments.get import get_departments

# Resource search fetchers (bounded, paginated)
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUBRIC_FLAG_NAMES = {"rubric_active"}


# ---------------------------------------------------------------------------
# resolve_rubric_context
# ---------------------------------------------------------------------------


async def resolve_rubric_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    rubric_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a rubric artifact into fully hydrated resources for the GET endpoint.

    Steps:
      1. Fetch artifact + draft in parallel -> merge IDs
      2. Parallel hydrate: get (selected) + search (suggestions) per resource
      3. Assemble ArtifactContext with ResourcePairs
    """
    user_dept_ids = user_department_ids or []

    # Step 1: fetch artifact + draft in parallel

    async def _fetch_artifacts() -> list:
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

    async def _fetch_drafts() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_rubric_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifacts(), _fetch_drafts())

    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None

    # Merge IDs: start from published, draft overrides if present
    merged = _merge_junction_ids(artifact, draft)
    draft_version = draft.version if draft else None
    active = artifact.active if artifact else True

    # Step 2: parallel hydrate — selected + suggestions for each resource

    async def _get_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, merged.name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                draft_id=group_id,
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                rubric=True,
            )

    async def _get_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, merged.description_ids, redis, bypass_cache
            )

    async def _search_descriptions() -> list:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                draft_id=group_id,
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                rubric=True,
            )

    async def _get_flags() -> list:
        async with pool.acquire() as conn:
            return await get_flags(conn, merged.flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=None,
                limit_count=50,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
                rubric=True,
            )

    async def _get_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(
                conn, merged.department_ids, redis, bypass_cache
            )

    async def _search_departments() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all" if rubric_id is None else "recent",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_points() -> list:
        async with pool.acquire() as conn:
            return await get_points(conn, merged.point_ids, redis, bypass_cache)

    async def _search_points() -> list:
        async with pool.acquire() as conn:
            return await search_points(
                conn,
                redis,
                exclude_ids=merged.point_ids,
                bypass_cache=bypass_cache,
                rubric=True,
            )

    async def _get_standard_groups() -> list:
        async with pool.acquire() as conn:
            return await get_standard_groups(
                conn, merged.standard_group_ids, redis, bypass_cache
            )

    async def _search_standard_groups() -> list:
        async with pool.acquire() as conn:
            return await search_standard_groups(
                conn,
                redis,
                exclude_ids=merged.standard_group_ids,
                bypass_cache=bypass_cache,
                rubric=True,
            )

    async def _get_standards() -> list:
        async with pool.acquire() as conn:
            return await get_standards(conn, merged.standard_ids, redis, bypass_cache)

    async def _search_standards() -> list:
        async with pool.acquire() as conn:
            return await search_standards(
                conn,
                redis,
                exclude_ids=merged.standard_ids,
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
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_points(),
        _search_points(),
        _get_standard_groups(),
        _search_standard_groups(),
        _get_standards(),
        _search_standards(),
    )

    # Filter flags to rubric-specific types
    flags_suggestions_filtered = [
        f for f in flags_suggestions if getattr(f, "name", None) in RUBRIC_FLAG_NAMES
    ]

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=active,
        group_id=group_id,
        draft_version=draft_version,
        resources={
            "names": ResourcePair(
                selected=names_selected, suggestions=names_suggestions
            ),
            "descriptions": ResourcePair(
                selected=descriptions_selected, suggestions=descriptions_suggestions
            ),
            "flags": ResourcePair(
                selected=flags_selected, suggestions=flags_suggestions_filtered
            ),
            "departments": ResourcePair(
                selected=departments_selected, suggestions=departments_suggestions
            ),
            "points": ResourcePair(
                selected=points_selected, suggestions=points_suggestions
            ),
            "standard_groups": ResourcePair(
                selected=standard_groups_selected,
                suggestions=standard_groups_suggestions,
            ),
            "standards": ResourcePair(
                selected=standards_selected, suggestions=standards_suggestions
            ),
        },
        entries={},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _MergedIds:
    """Merged junction IDs from artifact + draft."""

    name_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    point_ids: list[UUID]
    standard_group_ids: list[UUID]
    standard_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides."""
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    point_ids = list(artifact.point_ids or []) if artifact else []
    standard_group_ids = list(artifact.standard_group_ids or []) if artifact else []
    standard_ids = list(artifact.standard_ids or []) if artifact else []

    # Draft overrides (if present) — ignore profile_ids from draft
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
