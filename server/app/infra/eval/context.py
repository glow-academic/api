"""Resolve eval artifact context — merged junctions + hydrated resources.

Given an eval_id (and optional draft_id), fetches the published artifact
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
from app.tools.artifacts.eval.get import (
    get_evals as get_eval_artifacts,
)
from app.tools.entries.eval_drafts.get import get_eval_drafts

# Resource get fetchers (by known IDs)
from app.tools.resources.departments.get import get_departments

# Resource search fetchers (bounded, paginated)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.model_flags.get import get_model_flags
from app.tools.resources.model_flags.search import search_model_flags
from app.tools.resources.model_positions.get import get_model_positions
from app.tools.resources.model_positions.search import search_model_positions
from app.tools.resources.model_rubrics.get import get_model_rubrics
from app.tools.resources.model_rubrics.search import search_model_rubrics
from app.tools.resources.models.get import get_models
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVAL_FLAG_NAMES = {"eval_active", "dynamic", ""}


# ---------------------------------------------------------------------------
# resolve_eval_context
# ---------------------------------------------------------------------------


async def resolve_eval_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    eval_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve an eval artifact into fully hydrated resources for the GET endpoint.

    Steps:
      1. Fetch artifact + draft in parallel -> merge IDs
      2. Parallel hydrate: get (selected) + search (suggestions) per resource
      3. Assemble ArtifactContext with ResourcePairs
    """
    user_dept_ids = user_department_ids or []

    # Step 1: fetch artifact + draft in parallel

    async def _fetch_artifact() -> list:
        if not eval_id:
            return []
        async with pool.acquire() as conn:
            return await get_eval_artifacts(
                conn,
                [eval_id],
                active=None,
                names=True,
                descriptions=True,
                departments=True,
                flags=True,
                models=True,
                model_flags=True,
                model_rubrics=True,
                model_positions=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_eval_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())

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
                eval=True,
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
                eval=True,
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
                eval=True,
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
                suggest_source="all" if eval_id is None else "recent",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_models() -> list:
        async with pool.acquire() as conn:
            return await get_models(conn, merged.model_ids, redis, bypass_cache)

    async def _get_model_flags() -> list:
        async with pool.acquire() as conn:
            return await get_model_flags(
                conn, merged.model_flag_ids, redis, bypass_cache
            )

    async def _search_model_flags() -> list:
        async with pool.acquire() as conn:
            return await search_model_flags(
                conn,
                redis,
                exclude_ids=merged.model_flag_ids,
                bypass_cache=bypass_cache,
                eval=True,
            )

    async def _get_model_rubrics() -> list:
        async with pool.acquire() as conn:
            return await get_model_rubrics(
                conn, merged.model_rubric_ids, redis, bypass_cache
            )

    async def _search_model_rubrics() -> list:
        async with pool.acquire() as conn:
            return await search_model_rubrics(
                conn,
                redis,
                exclude_ids=merged.model_rubric_ids,
                bypass_cache=bypass_cache,
                eval=True,
            )

    async def _get_model_positions() -> list:
        async with pool.acquire() as conn:
            return await get_model_positions(
                conn, merged.model_position_ids, redis, bypass_cache
            )

    async def _search_model_positions() -> list:
        async with pool.acquire() as conn:
            return await search_model_positions(
                conn,
                redis,
                exclude_ids=merged.model_position_ids,
                bypass_cache=bypass_cache,
                eval=True,
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
        models_selected,
        model_flags_selected,
        model_flags_suggestions,
        model_rubrics_selected,
        model_rubrics_suggestions,
        model_positions_selected,
        model_positions_suggestions,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_models(),
        _get_model_flags(),
        _search_model_flags(),
        _get_model_rubrics(),
        _search_model_rubrics(),
        _get_model_positions(),
        _search_model_positions(),
    )

    # Filter flags to eval-specific types
    flags_suggestions_filtered = [
        f for f in flags_suggestions if getattr(f, "name", None) in EVAL_FLAG_NAMES
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
            "models": ResourcePair(selected=models_selected, suggestions=[]),
            "model_flags": ResourcePair(
                selected=model_flags_selected, suggestions=model_flags_suggestions
            ),
            "model_rubrics": ResourcePair(
                selected=model_rubrics_selected, suggestions=model_rubrics_suggestions
            ),
            "model_positions": ResourcePair(
                selected=model_positions_selected,
                suggestions=model_positions_suggestions,
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
    model_ids: list[UUID]
    model_flag_ids: list[UUID]
    model_rubric_ids: list[UUID]
    model_position_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides.

    Draft overrides published values. Ignores profile_ids and rubric_ids
    from draft (rubric junction has been dropped).
    """
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    model_ids = list(artifact.model_ids or []) if artifact else []
    model_flag_ids = list(artifact.model_flag_ids or []) if artifact else []
    model_rubric_ids = list(artifact.model_rubric_ids or []) if artifact else []
    model_position_ids = list(artifact.model_position_ids or []) if artifact else []

    # Draft overrides (if present) — ignore profile_ids and rubric_ids from draft
    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.model_ids:
            model_ids = list(draft.model_ids)
        # Note: draft does not have model_flag_ids, model_rubric_ids,
        # model_position_ids connections — those come only from artifact junctions

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        model_ids=model_ids,
        model_flag_ids=model_flag_ids,
        model_rubric_ids=model_rubric_ids,
        model_position_ids=model_position_ids,
    )


async def _empty() -> list:
    return []
