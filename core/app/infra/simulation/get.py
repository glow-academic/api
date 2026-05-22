"""Canonical shared simulation GET operation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.helpers import sorted_dedupe_by_id
from app.infra.simulation.context import (
    SCENARIO_FLAG_TYPES_ORDERED,
    resolve_simulation_context,
)
from app.infra.simulation.permissions import (
    SIMULATION_RESOURCES,
    compute_can_draft,
    compute_can_edit,
    compute_disabled_reason,
    compute_scenario_show_flags,
    has_access,
)
from app.infra.simulation.permissions_context import (
    resolve_simulation_permissions_context,
)
from app.infra.simulation.types import (
    GetSimulationApiResponse,
    SectionFilter,
    SimulationDepartment,
    SimulationDescriptionResource,
    SimulationFlagResource,
    SimulationNameResource,
    SimulationRubric,
    SimulationScenario,
    SimulationScenarioFlag,
    SimulationScenarioFlagOption,
    SimulationScenarioPosition,
    SimulationScenarioRubric,
    SimulationScenarioTimeLimit,
)
from app.infra.tool_graph import score_tools
from app.infra.server_timing import timed
from app.tools.resources.flags.search import search_flags

SECTIONS = (
    "names",
    "descriptions",
    "flags",
    "departments",
    "scenarios",
    "scenario_flags",
    "scenario_positions",
    "scenario_rubrics",
    "scenario_time_limits",
)


def _sf(
    filters: dict[str, SectionFilter | Any | None],
    section: str,
    attr: str,
    default=None,
):
    """Get a SectionFilter attribute for a section, with default."""
    sf = filters.get(section)
    if sf is None:
        return default
    if isinstance(sf, dict):
        return sf.get(attr, default)
    return getattr(sf, attr, default)


def _section_included(filters: dict[str, SectionFilter | Any | None], section: str) -> bool:
    return _sf(filters, section, "include", True) is not False


def _apply_section_filters(
    items: list | None,
    *,
    filters: dict[str, SectionFilter | Any | None],
    section: str,
) -> list | None:
    if items is None:
        return None
    if not _section_included(filters, section):
        return None
    if _sf(filters, section, "selected"):
        items = [item for item in items if getattr(item, "selected", False)]
    if _sf(filters, section, "suggested"):
        items = [item for item in items if getattr(item, "suggested", False)]
    return items


def _model_many_with_flags(
    *,
    items: list,
    model_cls,
    suggested_ids: set[UUID],
    selected_ids: set[UUID],
    pending_ids: set[UUID],
    transform=None,
    id_attr: str = "id",
    section: str,
    filters: dict[str, SectionFilter | Any | None],
) -> list | None:
    if not _section_included(filters, section):
        return None

    result = []
    seen: set[UUID] = set()
    for item in items:
        item_id = getattr(item, id_attr, None)
        if item_id is None or item_id in seen:
            continue
        seen.add(item_id)
        payload = transform(item) if transform else item.model_dump()
        payload["suggested"] = item_id in suggested_ids
        payload["selected"] = item_id in selected_ids
        payload["pending"] = item_id in pending_ids
        result.append(model_cls.model_validate(payload))
    return _apply_section_filters(result, filters=filters, section=section)


def _department_payload(item) -> dict[str, Any]:
    payload = item.model_dump()
    payload["department_id"] = payload.pop("id", None)
    return payload


def _scenario_payload(item) -> dict[str, Any]:
    payload = item.model_dump()
    payload["scenario_id"] = payload.pop("id", None)
    payload.update(
        compute_scenario_show_flags(
            problem_statement_enabled=item.problem_statement_enabled,
            objectives_enabled=item.objectives_enabled,
            video_enabled=item.video_enabled,
            images_enabled=item.images_enabled,
            questions_enabled=item.questions_enabled,
        )
    )
    return payload


def _flag_payload(item, *, selected: bool, suggested: bool, pending: bool) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": getattr(item, "name", None),
        "type": getattr(item, "type", None),
        "value": getattr(item, "value", None),
        "description": item.description,
        "icon_id": getattr(item, "icon_id", None),
        # Hydrated SVG markup from flag_icons.hydrate_flag_icons. Without
        # this, SimulationFlagResource.icon stays None and the client falls
        # back to the Power placeholder icon.
        "icon": getattr(item, "icon", None),
        "generated": item.generated,
        "selected": selected,
        "suggested": suggested,
        "pending": pending,
    }


def _scenario_flag_model_many(
    *,
    selected_items: list,
    suggested_items: list,
    pending_ids: set[UUID],
    filters: dict[str, SectionFilter | Any | None],
) -> list | None:
    if not _section_included(filters, "scenario_flags"):
        return None

    result: list[SimulationScenarioFlag] = []
    seen_pairs: set[tuple[UUID | None, UUID | None]] = set()

    for item in selected_items:
        pair = (item.scenario_id, item.flag_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        payload = item.model_dump()
        payload["selected"] = True
        payload["suggested"] = False
        payload["pending"] = item.id in pending_ids if item.id else False
        result.append(SimulationScenarioFlag.model_validate(payload))

    for item in suggested_items:
        pair = (item.scenario_id, item.flag_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        payload = item.model_dump()
        payload["selected"] = False
        payload["suggested"] = True
        payload["pending"] = False
        result.append(SimulationScenarioFlag.model_validate(payload))

    return _apply_section_filters(result, filters=filters, section="scenario_flags")


async def get_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    simulation_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | Any | None] | None = None,
    scenario_search: str | None = None,
    scenario_show_selected: bool | None = None,
    filter_scenario_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetSimulationApiResponse:
    """Resolve the canonical simulation artifact bundle for any surface."""
    effective_filters: dict[str, SectionFilter | Any | None] = dict(filters or {})
    sim_id = id or simulation_id

    # Retain legacy scenario filter inputs while callers migrate to nested SectionFilter.
    if "scenarios" not in effective_filters and (
        scenario_search is not None or scenario_show_selected is not None
    ):
        effective_filters["scenarios"] = SectionFilter(
            search=scenario_search,
            selected=scenario_show_selected,
        )
    for section in SECTIONS:
        effective_filters.setdefault(section, None)

    with timed("common"):
        common = await resolve_common_context(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            bypass_cache=bypass_cache,
        )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if group_id is None:
        with timed("group"):
            _gr = await resolve_group_impl(
                pool, redis,
                artifact_type="simulation",
                profile_id=profile_id,
                session_id=session_id,
                include_history=False,
            )
            group_id = _gr.group_id
    effective_group_id = group_id
    perms = None
    if sim_id is not None:
        with timed("permissions"):
            async with pool.acquire() as conn:
                perms = await resolve_simulation_permissions_context(conn, sim_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation {sim_id} not found",
            )
        if not has_access(
            common.profile.role_level,
            common.profile.department_ids,
            perms.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this simulation. It may be restricted to other departments.",
            )

    with timed("simulation_ctx"):
     simulation = await resolve_simulation_context(
        pool,
        redis,
        simulation_id=sim_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=common.profile.department_ids,
        scenario_search=scenario_search,
        filter_scenario_ids=filter_scenario_ids,
        filters=effective_filters,
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, SIMULATION_RESOURCES)
    profile = common.profile

    simulation_department_ids = [
        department.id
        for department in simulation.resources["departments"].selected
        if getattr(department, "id", None)
    ]
    cohort_usage_count = perms.cohort_usage_count if perms else 0

    can_edit = compute_can_edit(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        simulation_department_ids=simulation_department_ids,
        cohort_usage_count=cohort_usage_count,
        user_department_ids=profile.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        simulation_department_ids=simulation_department_ids,
        cohort_usage_count=cohort_usage_count,
        user_department_ids=profile.department_ids,
    )
    can_ai_generate = compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    )

    pending_ids = set(simulation.entries.get("pending_ids", set()) or set())

    all_names = sorted_dedupe_by_id(
        simulation.resources["names"].suggestions + simulation.resources["names"].selected
    )
    all_descriptions = sorted_dedupe_by_id(
        simulation.resources["descriptions"].suggestions
        + simulation.resources["descriptions"].selected
    )
    all_flags = sorted_dedupe_by_id(
        simulation.resources["flags"].suggestions + simulation.resources["flags"].selected
    )
    all_departments = sorted_dedupe_by_id(
        simulation.resources["departments"].suggestions
        + simulation.resources["departments"].selected
    )
    all_scenarios = sorted_dedupe_by_id(
        simulation.resources["scenarios"].suggestions
        + simulation.resources["scenarios"].selected
    )
    all_scenario_positions = sorted_dedupe_by_id(
        simulation.resources["scenario_positions"].suggestions
        + simulation.resources["scenario_positions"].selected
    )
    all_scenario_rubrics = sorted_dedupe_by_id(
        simulation.resources["scenario_rubrics"].suggestions
        + simulation.resources["scenario_rubrics"].selected
    )
    all_scenario_time_limits = sorted_dedupe_by_id(
        simulation.resources["scenario_time_limits"].suggestions
        + simulation.resources["scenario_time_limits"].selected
    )

    suggested_sets = {
        "names": {item.id for item in simulation.resources["names"].suggestions if item.id},
        "descriptions": {
            item.id for item in simulation.resources["descriptions"].suggestions if item.id
        },
        "flags": {item.id for item in simulation.resources["flags"].suggestions if item.id},
        "departments": {
            item.id for item in simulation.resources["departments"].suggestions if item.id
        },
        "scenarios": {
            item.id for item in simulation.resources["scenarios"].suggestions if item.id
        },
        "scenario_positions": {
            item.id for item in simulation.resources["scenario_positions"].suggestions if item.id
        },
        "scenario_rubrics": {
            item.id for item in simulation.resources["scenario_rubrics"].suggestions if item.id
        },
        "scenario_time_limits": {
            item.id for item in simulation.resources["scenario_time_limits"].suggestions
            if item.id
        },
    }
    selected_sets = {
        "names": {item.id for item in simulation.resources["names"].selected if item.id},
        "descriptions": {
            item.id for item in simulation.resources["descriptions"].selected if item.id
        },
        "flags": {item.id for item in simulation.resources["flags"].selected if item.id},
        "departments": {
            item.id for item in simulation.resources["departments"].selected if item.id
        },
        "scenarios": {
            item.id for item in simulation.resources["scenarios"].selected if item.id
        },
        "scenario_positions": {
            item.id for item in simulation.resources["scenario_positions"].selected if item.id
        },
        "scenario_rubrics": {
            item.id for item in simulation.resources["scenario_rubrics"].selected if item.id
        },
        "scenario_time_limits": {
            item.id for item in simulation.resources["scenario_time_limits"].selected
            if item.id
        },
    }

    names = _model_many_with_flags(
        items=all_names,
        model_cls=SimulationNameResource,
        suggested_ids=suggested_sets["names"],
        selected_ids=selected_sets["names"],
        pending_ids=pending_ids,
        section="names",
        filters=effective_filters,
    )
    descriptions = _model_many_with_flags(
        items=all_descriptions,
        model_cls=SimulationDescriptionResource,
        suggested_ids=suggested_sets["descriptions"],
        selected_ids=selected_sets["descriptions"],
        pending_ids=pending_ids,
        section="descriptions",
        filters=effective_filters,
    )

    flags = None
    if _section_included(effective_filters, "flags"):
        flags = [
            SimulationFlagResource.model_validate(
                _flag_payload(
                    item,
                    selected=item.id in selected_sets["flags"] if item.id else False,
                    suggested=item.id in suggested_sets["flags"] if item.id else False,
                    pending=item.id in pending_ids if item.id else False,
                )
            )
            for item in all_flags
            if item.id
        ]
        flags = _apply_section_filters(flags, filters=effective_filters, section="flags")

    departments = _model_many_with_flags(
        items=all_departments,
        model_cls=SimulationDepartment,
        suggested_ids=suggested_sets["departments"],
        selected_ids=selected_sets["departments"],
        pending_ids=pending_ids,
        transform=_department_payload,
        section="departments",
        filters=effective_filters,
    )
    scenarios = _model_many_with_flags(
        items=all_scenarios,
        model_cls=SimulationScenario,
        suggested_ids=suggested_sets["scenarios"],
        selected_ids=selected_sets["scenarios"],
        pending_ids=pending_ids,
        transform=_scenario_payload,
        section="scenarios",
        filters=effective_filters,
    )
    scenario_flags = _scenario_flag_model_many(
        selected_items=simulation.resources["scenario_flags"].selected,
        suggested_items=simulation.resources["scenario_flags"].suggestions,
        pending_ids=pending_ids,
        filters=effective_filters,
    )
    scenario_positions = _model_many_with_flags(
        items=all_scenario_positions,
        model_cls=SimulationScenarioPosition,
        suggested_ids=suggested_sets["scenario_positions"],
        selected_ids=selected_sets["scenario_positions"],
        pending_ids=pending_ids,
        section="scenario_positions",
        filters=effective_filters,
    )
    scenario_rubrics = _model_many_with_flags(
        items=all_scenario_rubrics,
        model_cls=SimulationScenarioRubric,
        suggested_ids=suggested_sets["scenario_rubrics"],
        selected_ids=selected_sets["scenario_rubrics"],
        pending_ids=pending_ids,
        section="scenario_rubrics",
        filters=effective_filters,
    )
    scenario_time_limits = _model_many_with_flags(
        items=all_scenario_time_limits,
        model_cls=SimulationScenarioTimeLimit,
        suggested_ids=suggested_sets["scenario_time_limits"],
        selected_ids=selected_sets["scenario_time_limits"],
        pending_ids=pending_ids,
        section="scenario_time_limits",
        filters=effective_filters,
    )

    rubrics = None
    if _section_included(effective_filters, "rubrics"):
        rubrics = [
            SimulationRubric.model_validate(item.model_dump())
            for item in simulation.resources["rubrics"].suggestions
        ]

    # Build scenario_flag_options cross-product: every (scenario × type × value).
    # The client groups these by (scenario_id, type) and toggles between the
    # two flag_ids (value=true/false) per group. We filter flags_resource to
    # the canonical scenario-flag type list so unrelated types (e.g.
    # simulation_active) don't leak into the per-scenario UI.
    scenario_flag_options: list[SimulationScenarioFlagOption] | None = None
    if _section_included(effective_filters, "scenario_flags"):
        async with pool.acquire() as conn:
            all_flag_rows = await search_flags(
                conn, redis, search=None, limit_count=500, bypass_cache=bypass_cache
            )
        scenario_type_set = set(SCENARIO_FLAG_TYPES_ORDERED)
        scoped_flag_rows = [
            f for f in all_flag_rows
            if (getattr(f, "type", None) or "") in scenario_type_set
        ]
        option_scenario_ids = [
            getattr(item, "id", None) or getattr(item, "scenario_id", None)
            for item in (simulation.resources["scenarios"].selected
                         + simulation.resources["scenarios"].suggestions)
            if getattr(item, "id", None) or getattr(item, "scenario_id", None)
        ]
        seen_sids: set = set()
        unique_sids = []
        for sid in option_scenario_ids:
            if sid and sid not in seen_sids:
                seen_sids.add(sid)
                unique_sids.append(sid)

        scenario_flag_options = []
        for sid in unique_sids:
            for f in scoped_flag_rows:
                scenario_flag_options.append(
                    SimulationScenarioFlagOption(
                        scenario_id=sid,
                        flag_id=getattr(f, "id", None),
                        type=getattr(f, "type", None),
                        value=getattr(f, "value", None),
                        name=getattr(f, "name", None),
                        description=getattr(f, "description", None),
                        icon=getattr(f, "icon", None),
                    )
                )

    names_has_tools = scores.has_any.get("names", False)
    basic_show_ai_generate = bool(can_ai_generate and names_has_tools)

    with timed("build"):
     return GetSimulationApiResponse(
        actor_name=profile.name,
        simulation_exists=simulation.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        # Draft label sourced from ``entries['draft_name']`` (set by
        # ``resolve_simulation_context``). ``None`` when no draft was active.
        draft_name=simulation.entries.get("draft_name") if simulation.entries else None,
        show_ai_generate=can_ai_generate,
        basic_show_ai_generate=basic_show_ai_generate,
        names=names,
        descriptions=descriptions,
        flags=flags,
        departments=departments,
        scenarios=scenarios,
        scenario_flags=scenario_flags,
        scenario_flag_options=scenario_flag_options,
        scenario_positions=scenario_positions,
        scenario_rubrics=scenario_rubrics,
        scenario_time_limits=scenario_time_limits,
        rubrics=rubrics,
    )
