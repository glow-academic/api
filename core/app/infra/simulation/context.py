"""Resolve simulation artifact context — merged junctions + hydrated resources.

Given a simulation_id (and optional draft_id), fetches the published artifact
and draft entry, merges junction IDs (draft overrides published), then
hydrates all resources in parallel (selected + suggestions).

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Artifact + draft fetchers
from app.tools.artifacts.simulation.get import (
    get_simulations as get_simulation_artifacts,
)
from app.tools.entries.simulation_drafts.get import get_simulation_drafts

# Resource get fetchers (by known IDs)
from app.tools.resources.departments.get import get_departments

# Resource search fetchers (bounded, paginated)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.scenario_flags.get import get_scenario_flags
from app.tools.resources.scenario_positions.get import get_scenario_positions
from app.tools.resources.scenario_positions.search import (
    search_scenario_positions,
)
from app.tools.resources.scenario_rubrics.get import get_scenario_rubrics
from app.tools.resources.scenario_rubrics.search import (
    search_scenario_rubrics,
)
from app.tools.resources.scenario_time_limits.get import (
    get_scenario_time_limits,
)
from app.tools.resources.scenario_time_limits.search import (
    search_scenario_time_limits,
)
from app.tools.resources.scenarios.get import (
    get_scenarios as get_scenario_resources,
)
from app.tools.resources.scenarios.search import (
    search_scenarios as search_scenario_resources,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIMULATION_FLAG_TYPES_ORDERED = ["simulation_active", "practice"]

SCENARIO_FLAG_TYPES_ORDERED = [
    "audio_enabled",
    "text_enabled",
    "copy_paste_allowed",
    "hints_enabled",
    "show_problem_statement",
    "show_objectives",
    "show_images",
    "analyses_enabled",
    "strengths_enabled",
    "improvements_enabled",
    "replacements_enabled",
    "use_custom",
    "use_previous",
]


class SimulationScenarioFlag(BaseModel):
    """Infra-local scenario flag option shape used during context assembly."""

    id: UUID | None = None
    scenario_id: UUID | None = None
    flag_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    generated: bool | None = None


# ---------------------------------------------------------------------------
# resolve_simulation_context
# ---------------------------------------------------------------------------


async def resolve_simulation_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    simulation_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    scenario_search: str | None = None,
    filter_scenario_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a simulation artifact into fully hydrated resources.

    Steps:
      1. Fetch artifact + draft in parallel → merge IDs
      2. Parallel hydrate: get (selected) + search (suggestions) per resource
      3. Domain-specific: scenario flags cross-product
      4. Assemble ArtifactContext with ResourcePairs
    """
    user_dept_ids = user_department_ids or []

    # Step 1: fetch artifact + draft in parallel

    async def _fetch_artifact() -> list:
        if not simulation_id:
            return []
        async with pool.acquire() as conn:
            return await get_simulation_artifacts(
                conn,
                [simulation_id],
                active=None,
                names=True,
                descriptions=True,
                departments=True,
                flags=True,
                scenarios=True,
                scenario_flags=True,
                scenario_positions=True,
                scenario_rubrics=True,
                scenario_time_limits=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_simulation_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())

    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None

    # Merge IDs: start from published, draft overrides if present
    merged = _merge_junction_ids(artifact, draft)
    draft_version = draft.version if draft else None

    # Effective scenario IDs for sub-resources (filter overrides)
    effective_scenario_ids = filter_scenario_ids or merged.scenario_ids

    # Step 2: parallel hydrate — selected + suggestions for each resource
    # Each branch acquires its own connection from the pool.

    async def _get_names_selected() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, merged.name_ids, redis, bypass_cache)

    async def _search_names_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                draft_id=group_id,
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                simulation=True,
            )

    async def _get_descriptions_selected() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, merged.description_ids, redis, bypass_cache
            )

    async def _search_descriptions_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                draft_id=group_id,
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                simulation=True,
            )

    async def _search_flags_all() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=None,
                limit_count=50,
                offset_count=0,
                exclude_ids=None,
                bypass_cache=bypass_cache,
                simulation=True,
            )

    async def _get_departments_selected() -> list:
        async with pool.acquire() as conn:
            return await get_departments(
                conn, merged.department_ids, redis, bypass_cache=bypass_cache
            )

    async def _search_departments_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all" if simulation_id is None else "recent",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_scenarios_selected() -> list:
        async with pool.acquire() as conn:
            return await get_scenario_resources(
                conn, merged.scenario_ids, redis, bypass_cache
            )

    async def _search_scenarios_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_scenario_resources(
                conn,
                redis,
                search=scenario_search,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all",
                exclude_ids=merged.scenario_ids,
                bypass_cache=bypass_cache,
                simulation=True,
            )

    async def _get_scenario_flags_selected() -> list:
        async with pool.acquire() as conn:
            return await get_scenario_flags(
                conn, merged.scenario_flag_ids, redis, bypass_cache
            )

    async def _search_scenario_flag_types_all() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=None,
                limit_count=50,
                offset_count=0,
                exclude_ids=None,
                bypass_cache=bypass_cache,
            )

    async def _get_scenario_positions_selected() -> list:
        async with pool.acquire() as conn:
            return await get_scenario_positions(
                conn, merged.scenario_position_ids, redis, bypass_cache
            )

    async def _search_scenario_positions_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_scenario_positions(
                conn,
                redis,
                scenario_ids=effective_scenario_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_scenario_rubrics_selected() -> list:
        async with pool.acquire() as conn:
            return await get_scenario_rubrics(
                conn, merged.scenario_rubric_ids, redis, bypass_cache
            )

    async def _search_scenario_rubrics_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_scenario_rubrics(
                conn,
                redis,
                scenario_ids=effective_scenario_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_scenario_time_limits_selected() -> list:
        async with pool.acquire() as conn:
            return await get_scenario_time_limits(
                conn, merged.scenario_time_limit_ids, redis, bypass_cache
            )

    async def _search_scenario_time_limits_suggestions() -> list:
        async with pool.acquire() as conn:
            return await search_scenario_time_limits(
                conn,
                redis,
                scenario_ids=effective_scenario_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_rubrics_catalog() -> list:
        async with pool.acquire() as conn:
            return await get_rubrics(conn, None, redis, bypass_cache)

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        flags_all,
        departments_selected,
        departments_suggestions,
        scenarios_selected,
        scenarios_suggestions,
        scenario_flags_selected,
        scenario_flag_types_all,
        scenario_positions_selected,
        scenario_positions_suggestions,
        scenario_rubrics_selected,
        scenario_rubrics_suggestions,
        scenario_time_limits_selected,
        scenario_time_limits_suggestions,
        rubrics_catalog,
    ) = await asyncio.gather(
        _get_names_selected(),
        _search_names_suggestions(),
        _get_descriptions_selected(),
        _search_descriptions_suggestions(),
        _search_flags_all(),
        _get_departments_selected(),
        _search_departments_suggestions(),
        _get_scenarios_selected(),
        _search_scenarios_suggestions(),
        _get_scenario_flags_selected(),
        _search_scenario_flag_types_all(),
        _get_scenario_positions_selected(),
        _search_scenario_positions_suggestions(),
        _get_scenario_rubrics_selected(),
        _search_scenario_rubrics_suggestions(),
        _get_scenario_time_limits_selected(),
        _search_scenario_time_limits_suggestions(),
        _get_rubrics_catalog(),
    )

    # Order simulation flags by SIMULATION_FLAG_TYPES_ORDERED
    flags_by_type = {f.type: f for f in flags_all}
    flags_ordered = [
        flags_by_type[t] for t in SIMULATION_FLAG_TYPES_ORDERED if t in flags_by_type
    ]
    flags_selected = [f for f in flags_ordered if f.id in set(merged.flag_ids)]

    # Order scenario flag types by SCENARIO_FLAG_TYPES_ORDERED
    sf_types_by_type = {f.type: f for f in scenario_flag_types_all}
    scenario_flag_types_ordered = [
        sf_types_by_type[t]
        for t in SCENARIO_FLAG_TYPES_ORDERED
        if t in sf_types_by_type
    ]

    # Build scenario flags cross-product: all scenarios × all flag types
    all_scenario_ids = [
        s.id for s in scenarios_selected + scenarios_suggestions if s.id
    ]
    sf_existing: set[tuple[UUID, UUID]] = set()
    for sf in scenario_flags_selected:
        if sf.scenario_id and sf.flag_id:
            sf_existing.add((sf.scenario_id, sf.flag_id))

    scenario_flags_suggestions: list[SimulationScenarioFlag] = []
    for sid in all_scenario_ids:
        for flag in scenario_flag_types_ordered:
            if not flag.id or (sid, flag.id) in sf_existing:
                continue
            scenario_flags_suggestions.append(
                SimulationScenarioFlag(
                    id=None,
                    scenario_id=sid,
                    flag_id=flag.id,
                    name=flag.name,
                    description=flag.description,
                    icon=flag.icon,
                    generated=False,
                )
            )

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
            "flags": ResourcePair(selected=flags_selected, suggestions=flags_ordered),
            "departments": ResourcePair(
                selected=departments_selected, suggestions=departments_suggestions
            ),
            "scenarios": ResourcePair(
                selected=scenarios_selected, suggestions=scenarios_suggestions
            ),
            "scenario_flags": ResourcePair(
                selected=list(scenario_flags_selected),
                suggestions=scenario_flags_suggestions,
            ),
            "scenario_positions": ResourcePair(
                selected=list(scenario_positions_selected),
                suggestions=list(scenario_positions_suggestions),
            ),
            "scenario_rubrics": ResourcePair(
                selected=list(scenario_rubrics_selected),
                suggestions=list(scenario_rubrics_suggestions),
            ),
            "scenario_time_limits": ResourcePair(
                selected=list(scenario_time_limits_selected),
                suggestions=list(scenario_time_limits_suggestions),
            ),
            "rubrics": ResourcePair(selected=[], suggestions=rubrics_catalog),
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
    scenario_ids: list[UUID]
    scenario_flag_ids: list[UUID]
    scenario_position_ids: list[UUID]
    scenario_rubric_ids: list[UUID]
    scenario_time_limit_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides."""
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    scenario_ids = list(artifact.scenario_ids or []) if artifact else []
    scenario_flag_ids = list(artifact.scenario_flag_ids or []) if artifact else []
    scenario_position_ids = (
        list(artifact.scenario_position_ids or []) if artifact else []
    )
    scenario_rubric_ids = list(artifact.scenario_rubric_ids or []) if artifact else []
    scenario_time_limit_ids = (
        list(artifact.scenario_time_limit_ids or []) if artifact else []
    )

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.scenario_ids:
            scenario_ids = list(draft.scenario_ids)
        if draft.scenario_flag_ids:
            scenario_flag_ids = list(draft.scenario_flag_ids)
        if draft.scenario_position_ids:
            scenario_position_ids = list(draft.scenario_position_ids)
        if draft.scenario_rubric_ids:
            scenario_rubric_ids = list(draft.scenario_rubric_ids)
        if draft.scenario_time_limit_ids:
            scenario_time_limit_ids = list(draft.scenario_time_limit_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        scenario_ids=scenario_ids,
        scenario_flag_ids=scenario_flag_ids,
        scenario_position_ids=scenario_position_ids,
        scenario_rubric_ids=scenario_rubric_ids,
        scenario_time_limit_ids=scenario_time_limit_ids,
    )


async def _empty() -> list:
    return []
