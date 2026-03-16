"""Resolve cohort artifact context — merged junctions + hydrated resources.

Given a cohort_id (and optional draft_id), fetches the published artifact
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
from app.tools.artifacts.cohort.get import (
    get_cohorts as get_cohort_artifacts,
)
from app.tools.entries.cohort_drafts.get import get_cohort_drafts

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
from app.tools.resources.personas.search import search_personas
from app.tools.resources.profile_personas.get import get_profile_personas
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.profiles.search import search_profiles
from app.tools.resources.simulation_availability.get import (
    get_simulation_availability,
)
from app.tools.resources.simulation_positions.get import (
    get_simulation_positions,
)
from app.tools.resources.simulations.get import get_simulations
from app.tools.resources.simulations.search import search_simulations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COHORT_FLAG_TYPES = {"cohort_active"}


# ---------------------------------------------------------------------------
# resolve_cohort_context
# ---------------------------------------------------------------------------


async def resolve_cohort_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    cohort_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    descriptions_search: str | None = None,
    simulation_search: str | None = None,
    simulation_show_selected: bool | None = None,
    profile_search: str | None = None,
    profile_show_selected: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a cohort artifact into fully hydrated resources.

    Steps:
      1. Fetch artifact + draft in parallel → merge IDs
      2. Parallel hydrate: get (selected) + search (suggestions) per resource
      3. Assemble ArtifactContext with ResourcePairs
    """
    user_dept_ids = user_department_ids or []

    # Step 1: fetch artifact + draft in parallel

    async def _fetch_artifact() -> list:
        if not cohort_id:
            return []
        async with pool.acquire() as conn:
            return await get_cohort_artifacts(
                conn,
                [cohort_id],
                active=None,
                names=True,
                descriptions=True,
                departments=True,
                flags=True,
                simulations=True,
                simulation_positions=True,
                simulation_availability=True,
                profiles=True,
                profile_personas=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_cohort_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())

    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None

    # Merge IDs: start from published, draft overrides if present
    merged = _merge_junction_ids(artifact, draft)
    draft_version = draft.version if draft else None

    # Step 2: parallel hydrate — selected + suggestions for each resource

    async def _fetch_names_selected() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, merged.name_ids, redis, bypass_cache)

    async def _fetch_names_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                draft_id=group_id,
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _fetch_descriptions_selected() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, merged.description_ids, redis, bypass_cache
            )

    async def _fetch_descriptions_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=descriptions_search,
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _fetch_flags_selected() -> list:
        async with pool.acquire() as conn:
            return await get_flags(conn, merged.flag_ids, redis, bypass_cache)

    async def _fetch_flags_all() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=None,
                limit_count=50,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _fetch_departments_selected() -> list:
        async with pool.acquire() as conn:
            return await get_departments(
                conn, merged.department_ids, redis, bypass_cache=bypass_cache
            )

    async def _fetch_departments_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _fetch_simulations_selected() -> list:
        async with pool.acquire() as conn:
            return await get_simulations(
                conn, merged.simulation_ids, redis, bypass_cache=bypass_cache
            )

    async def _fetch_simulations_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_simulations(
                conn,
                redis,
                search=simulation_search,
                limit_count=20,
                offset_count=0,
                draft_id=group_id,
                suggest_source="selected" if simulation_show_selected else "all",
                exclude_ids=merged.simulation_ids,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _fetch_simulation_positions() -> list:
        if not merged.simulation_position_ids:
            return []
        async with pool.acquire() as conn:
            return await get_simulation_positions(
                conn, merged.simulation_position_ids, redis, bypass_cache=bypass_cache
            )

    async def _fetch_simulation_availability() -> list:
        if not merged.simulation_availability_ids:
            return []
        async with pool.acquire() as conn:
            return await get_simulation_availability(
                conn,
                merged.simulation_availability_ids,
                redis,
                bypass_cache=bypass_cache,
            )

    async def _fetch_profiles_selected() -> list:
        if not merged.profile_ids:
            return []
        async with pool.acquire() as conn:
            return await get_profiles(
                conn, merged.profile_ids, redis, bypass_cache=bypass_cache
            )

    async def _fetch_profiles_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_profiles(
                conn,
                redis,
                search=profile_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.profile_ids or [],
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
            )

    async def _fetch_profile_personas() -> list:
        if not merged.profile_persona_ids:
            return []
        async with pool.acquire() as conn:
            return await get_profile_personas(
                conn, merged.profile_persona_ids, redis, bypass_cache=bypass_cache
            )

    async def _fetch_personas_catalog() -> list:
        async with pool.acquire() as conn:
            return await search_personas(
                conn,
                redis,
                search=None,
                limit_count=100,
                offset_count=0,
                bypass_cache=bypass_cache,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        flags_selected,
        flags_all,
        departments_selected,
        departments_suggestions,
        simulations_selected,
        simulations_suggestions,
        simulation_positions_selected,
        simulation_availability_selected,
        profiles_selected,
        profiles_suggestions,
        profile_personas_selected,
        personas_catalog,
    ) = await asyncio.gather(
        _fetch_names_selected(),
        _fetch_names_suggestions(),
        _fetch_descriptions_selected(),
        _fetch_descriptions_suggestions(),
        _fetch_flags_selected(),
        _fetch_flags_all(),
        _fetch_departments_selected(),
        _fetch_departments_suggestions(),
        _fetch_simulations_selected(),
        _fetch_simulations_suggestions(),
        _fetch_simulation_positions(),
        _fetch_simulation_availability(),
        _fetch_profiles_selected(),
        _fetch_profiles_suggestions(),
        _fetch_profile_personas(),
        _fetch_personas_catalog(),
    )

    # Filter flags to cohort-specific types
    flags_suggestions = [f for f in flags_all if f.type in COHORT_FLAG_TYPES]

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=artifact.active if artifact else True,
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
                selected=flags_selected, suggestions=flags_suggestions
            ),
            "departments": ResourcePair(
                selected=departments_selected, suggestions=departments_suggestions
            ),
            "simulations": ResourcePair(
                selected=simulations_selected, suggestions=simulations_suggestions
            ),
            "simulation_positions": ResourcePair(
                selected=list(simulation_positions_selected), suggestions=[]
            ),
            "simulation_availability": ResourcePair(
                selected=list(simulation_availability_selected), suggestions=[]
            ),
            "profiles": ResourcePair(
                selected=list(profiles_selected), suggestions=list(profiles_suggestions)
            ),
            "profile_personas": ResourcePair(
                selected=list(profile_personas_selected), suggestions=[]
            ),
            "personas": ResourcePair(selected=[], suggestions=personas_catalog),
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
    simulation_ids: list[UUID]
    simulation_position_ids: list[UUID]
    simulation_availability_ids: list[UUID]
    profile_ids: list[UUID]
    profile_persona_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides."""
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    simulation_ids = list(artifact.simulation_ids or []) if artifact else []
    simulation_position_ids = (
        list(artifact.simulation_position_ids or []) if artifact else []
    )
    simulation_availability_ids = (
        list(artifact.simulation_availability_ids or []) if artifact else []
    )
    profile_ids = list(artifact.profiles_ids or []) if artifact else []
    profile_persona_ids = list(artifact.profile_persona_ids or []) if artifact else []

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.simulation_ids:
            simulation_ids = list(draft.simulation_ids)
        if draft.simulation_position_ids:
            simulation_position_ids = list(draft.simulation_position_ids)
        if draft.simulation_availability_ids:
            simulation_availability_ids = list(draft.simulation_availability_ids)
        if draft.profile_ids:
            profile_ids = list(draft.profile_ids)
        if draft.profile_persona_ids:
            profile_persona_ids = list(draft.profile_persona_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        simulation_ids=simulation_ids,
        simulation_position_ids=simulation_position_ids,
        simulation_availability_ids=simulation_availability_ids,
        profile_ids=profile_ids,
        profile_persona_ids=profile_persona_ids,
    )


async def _empty() -> list:
    return []
