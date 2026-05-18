"""Resolve cohort artifact context - merged junctions + hydrated resources.

Given a cohort_id (and optional draft_id), fetches the published artifact
and draft entry, merges junction IDs (draft overrides published), then
hydrates all resources in parallel (selected + suggestions).

Composes existing black-box fetchers - no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.cohort.get import get_cohorts as get_cohort_artifacts
from app.tools.entries.cohort_drafts.get import get_cohort_drafts
from app.tools.resources.departments.get import get_departments
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
from app.tools.resources.simulation_availability.search import (
    search_simulation_availability,
)
from app.tools.resources.simulation_positions.get import get_simulation_positions
from app.tools.resources.simulation_positions.search import (
    search_simulation_positions,
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
    filters: dict[str, Any | None] | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a cohort artifact into fully hydrated resources."""
    user_dept_ids = user_department_ids or []
    section_filters = filters or {}

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

    merged = _merge_junction_ids(artifact, draft)
    active = artifact.active if artifact else True

    def _sf(section: str, attr: str, default=None):
        sf = section_filters.get(section)
        if sf is None:
            return default
        if isinstance(sf, dict):
            return sf.get(attr, default)
        return getattr(sf, attr, default)

    def _include(section: str) -> bool:
        return _sf(section, "include", True) is not False

    def _limit(section: str, default: int) -> int:
        value = _sf(section, "limit", None)
        return default if value is None else value

    # Step 2: parallel hydrate - selected + suggestions for each resource

    async def _get_names() -> list:
        if not _include("names"):
            return []
        return await get_names(pool, merged.name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        if not _include("names"):
            return []
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                search=_sf("names", "search"),
                limit_count=_limit("names", 20),
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _get_descriptions() -> list:
        if not _include("descriptions"):
            return []
        return await get_descriptions(pool, merged.description_ids, redis, bypass_cache
        )

    async def _search_descriptions() -> list:
        if not _include("descriptions"):
            return []
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=_sf("descriptions", "search"),
                limit_count=_limit("descriptions", 20),
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _get_flags() -> list:
        if not _include("flags"):
            return []
        return await get_flags(pool, merged.flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        if not _include("flags"):
            return []
        async with pool.acquire() as conn:
            # Don't filter on cohort_flags_junction — new cohorts have no
            # junction rows yet. COHORT_FLAG_TYPES post-filter is the real
            # catalog narrowing downstream.
            return await search_flags(
                conn,
                redis,
                search=_sf("flags", "search"),
                limit_count=_limit("flags", 200),
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_departments() -> list:
        if not _include("departments"):
            return []
        return await get_departments(
            pool, merged.department_ids, redis, bypass_cache=bypass_cache
        )

    async def _search_departments() -> list:
        if not _include("departments"):
            return []
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=_sf("departments", "search"),
                limit_count=_limit("departments", 20),
                offset_count=0,
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=merged.department_ids,
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _get_simulations() -> list:
        if not _include("simulations"):
            return []
        return await get_simulations(pool, merged.simulation_ids, redis, bypass_cache=bypass_cache
        )

    async def _search_simulations() -> list:
        if not _include("simulations"):
            return []
        async with pool.acquire() as conn:
            return await search_simulations(
                conn,
                redis,
                search=_sf("simulations", "search"),
                limit_count=_limit("simulations", 20),
                offset_count=0,
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=merged.simulation_ids,
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _get_simulation_positions() -> list:
        if not _include("simulation_positions"):
            return []
        if not merged.simulation_position_ids:
            return []
        return await get_simulation_positions(pool, merged.simulation_position_ids, redis, bypass_cache=bypass_cache
        )

    async def _search_simulation_positions() -> list:
        if not _include("simulation_positions"):
            return []
        async with pool.acquire() as conn:
            return await search_simulation_positions(
                conn,
                redis,
                limit_count=_limit("simulation_positions", 20),
                offset_count=0,
                exclude_ids=merged.simulation_position_ids,
                simulation_ids=merged.simulation_ids or None,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _get_simulation_availability() -> list:
        if not _include("simulation_availability"):
            return []
        if not merged.simulation_availability_ids:
            return []
        return await get_simulation_availability(pool,
            merged.simulation_availability_ids,
            redis,
            bypass_cache=bypass_cache,
        )

    async def _search_simulation_availability() -> list:
        if not _include("simulation_availability"):
            return []
        async with pool.acquire() as conn:
            return await search_simulation_availability(
                conn,
                redis,
                search=_sf("simulation_availability", "search"),
                limit_count=_limit("simulation_availability", 20),
                offset_count=0,
                exclude_ids=merged.simulation_availability_ids,
                simulation_ids=merged.simulation_ids or None,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _get_profiles() -> list:
        if not _include("profiles"):
            return []
        if not merged.profile_ids:
            return []
        return await get_profiles(
            pool, merged.profile_ids, redis, bypass_cache=bypass_cache
        )

    async def _search_profiles() -> list:
        if not _include("profiles"):
            return []
        async with pool.acquire() as conn:
            return await search_profiles(
                conn,
                redis,
                search=_sf("profiles", "search"),
                limit_count=_limit("profiles", 20),
                offset_count=0,
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=merged.profile_ids or [],
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
                cohort=True,
            )

    async def _get_profile_personas() -> list:
        if not _include("profile_personas"):
            return []
        if not merged.profile_persona_ids:
            return []
        return await get_profile_personas(pool, merged.profile_persona_ids, redis, bypass_cache=bypass_cache
        )

    async def _search_personas() -> list:
        if not _include("personas"):
            return []
        async with pool.acquire() as conn:
            return await search_personas(
                conn,
                redis,
                search=_sf("personas", "search"),
                limit_count=_limit("personas", 100),
                offset_count=0,
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=[],
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
                persona=True,
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
        simulations_selected,
        simulations_suggestions,
        simulation_positions_selected,
        simulation_positions_suggestions,
        simulation_availability_selected,
        simulation_availability_suggestions,
        profiles_selected,
        profiles_suggestions,
        profile_personas_selected,
        personas_catalog,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_simulations(),
        _search_simulations(),
        _get_simulation_positions(),
        _search_simulation_positions(),
        _get_simulation_availability(),
        _search_simulation_availability(),
        _get_profiles(),
        _search_profiles(),
        _get_profile_personas(),
        _search_personas(),
    )

    flags_suggestions = [
        flag for flag in flags_suggestions if getattr(flag, "type", None) in COHORT_FLAG_TYPES
    ]

    # Hydrate SVG icons onto each flag (icon_id → icon markup).
    async with pool.acquire() as conn:
        await hydrate_flag_icons(
            flags_selected + flags_suggestions, conn, redis, bypass_cache
        )

    # Cohort draft black-boxes do not expose inactive connections, so pending_ids
    # remain empty until the draft layer grows that support.
    pending_ids: set[UUID] = set()
    if draft:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(draft.pending_simulation_ids or [])
        pending_ids.update(draft.pending_simulation_position_ids or [])
        pending_ids.update(draft.pending_simulation_availability_ids or [])
        pending_ids.update(draft.pending_profile_ids or [])
        pending_ids.update(draft.pending_profile_persona_ids or [])

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=artifact.active if artifact else True,
        group_id=group_id,
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
                selected=simulation_positions_selected,
                suggestions=simulation_positions_suggestions,
            ),
            "simulation_availability": ResourcePair(
                selected=simulation_availability_selected,
                suggestions=simulation_availability_suggestions,
            ),
            "profiles": ResourcePair(
                selected=profiles_selected, suggestions=profiles_suggestions
            ),
            "profile_personas": ResourcePair(
                selected=profile_personas_selected, suggestions=[]
            ),
            "personas": ResourcePair(selected=[], suggestions=personas_catalog),
        },
        entries={"draft_name": draft.name if draft else None, "pending_ids": pending_ids},
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
