"""Canonical shared simulation get operation.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_simulation_permissions_context — access check (404, 403, fail fast)
  3. resolve_simulation_context — artifact + draft → merged + hydrated resources
  4. score_tools — tool graph + artifact resources → per-resource tool picks
  5. Pure Python — permissions, show/required flags, response assembly
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.simulation.context import resolve_simulation_context
from app.infra.simulation.permissions import (
    SIMULATION_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_scenario_flags_required,
    compute_scenario_positions_required,
    compute_scenario_rubrics_required,
    compute_scenario_show_flags,
    compute_scenario_time_limits_required,
    compute_scenarios_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_scenario_flags,
    compute_show_scenario_positions,
    compute_show_scenario_rubrics,
    compute_show_scenario_time_limits,
    compute_show_scenarios,
    has_access,
)
from app.infra.simulation.permissions_context import (
    resolve_simulation_permissions_context,
)
from app.infra.tool_graph import score_tools
from app.infra.simulation.types import (
    GetSimulationApiResponse,
    SimulationDepartment,
    SimulationDepartmentSection,
    SimulationDescriptionSection,
    SimulationFlagConfig,
    SimulationFlagSection,
    SimulationNameSection,
    SimulationScenario,
    SimulationScenarioFlagSection,
    SimulationScenarioPositionSection,
    SimulationScenarioRubricSection,
    SimulationScenarioSection,
    SimulationScenarioTimeLimitSection,
)

# ---------------------------------------------------------------------------
# get_simulation_impl — composable infra architecture
# ---------------------------------------------------------------------------


def _serialize_model(item):
    if item is None:
        return None
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return item


def _serialize_models(items: list) -> list:
    return [_serialize_model(item) for item in items]


async def get_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    simulation_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    scenario_search: str | None = None,
    filter_scenario_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
) -> GetSimulationApiResponse:
    """Simulation GET using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) → profile, tool_graph, runs
      2. resolve_simulation_permissions_context → access check (404, 403, fail fast)
      3. resolve_simulation_context(simulation_id, draft_id, ...) → hydrated resources
      4. score_tools(tool_graph, SIMULATION_RESOURCES) → per-resource tool picks
      5. Pure Python: permissions, show/required/AI flags, response assembly
    """

    # ── Step 1: Common context (profile → tool_graph + runs) ──────────────

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="simulation",
        bypass_cache=bypass_cache,
    )

    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    group_id = group_id or common.profile.group_id
    profile = common.profile

    # ── Step 2: Permissions check (fail fast before full hydration) ────────

    perms = None
    if simulation_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_simulation_permissions_context(conn, simulation_id)

        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation {simulation_id} not found",
            )

        if not has_access(profile.role, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this simulation. "
                "It may be restricted to other departments.",
            )

    # ── Step 3: Simulation artifact context ─────────────────────────────

    simulation = await resolve_simulation_context(
        pool,
        redis,
        simulation_id=simulation_id,
        group_id=group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        scenario_search=scenario_search,
        filter_scenario_ids=filter_scenario_ids,
        bypass_cache=bypass_cache,
    )

    # ── Step 4: Tool scoring ──────────────────────────────────────────────

    scores = score_tools(common.tool_graph, SIMULATION_RESOURCES)

    tool_ids_map: dict[str, UUID | None] = {
        r: (scores.best[r].tool_id if scores.best.get(r) else None)
        for r in SIMULATION_RESOURCES
    }

    # ── Step 5: Permissions ───────────────────────────────────────────────

    simulation_department_ids = [
        d.id for d in simulation.resources["departments"].selected
    ]
    cohort_usage_count = perms.cohort_usage_count if perms else 0

    can_edit = compute_can_edit(
        user_role=profile.role,
        simulation_department_ids=simulation_department_ids,
        cohort_usage_count=cohort_usage_count,
        user_department_ids=profile.department_ids,
    )

    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        simulation_department_ids=simulation_department_ids,
        cohort_usage_count=cohort_usage_count,
        user_department_ids=profile.department_ids,
    )

    # ── Step 6: Show / Required / AI flags ────────────────────────────────

    all_departments = dedupe_by_id(
        simulation.resources["departments"].selected
        + simulation.resources["departments"].suggestions
    )
    all_scenarios = dedupe_by_id(
        simulation.resources["scenarios"].selected
        + simulation.resources["scenarios"].suggestions
    )
    all_scenario_flags = (
        simulation.resources["scenario_flags"].selected
        + simulation.resources["scenario_flags"].suggestions
    )
    all_scenario_positions = dedupe_by_id(
        simulation.resources["scenario_positions"].selected
        + simulation.resources["scenario_positions"].suggestions
    )
    all_scenario_rubrics = dedupe_by_id(
        simulation.resources["scenario_rubrics"].selected
        + simulation.resources["scenario_rubrics"].suggestions
    )
    all_scenario_time_limits = dedupe_by_id(
        simulation.resources["scenario_time_limits"].selected
        + simulation.resources["scenario_time_limits"].suggestions
    )

    effective_scenario_ids = filter_scenario_ids or [
        s.id for s in simulation.resources["scenarios"].selected if s.id
    ]

    names_has_tools = scores.has_any.get("names", False)

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "scenarios": compute_show_scenarios(len(all_scenarios)),
        "scenario_flags": compute_show_scenario_flags(
            effective_scenario_ids, len(all_scenario_flags), len(all_scenarios)
        ),
        "scenario_positions": compute_show_scenario_positions(
            effective_scenario_ids, len(all_scenario_positions), len(all_scenarios)
        ),
        "scenario_rubrics": compute_show_scenario_rubrics(
            effective_scenario_ids, len(all_scenario_rubrics), len(all_scenarios)
        ),
        "scenario_time_limits": compute_show_scenario_time_limits(
            effective_scenario_ids, len(all_scenario_time_limits), len(all_scenarios)
        ),
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "scenarios": compute_scenarios_required(),
        "scenario_flags": compute_scenario_flags_required(),
        "scenario_positions": compute_scenario_positions_required(),
        "scenario_rubrics": compute_scenario_rubrics_required(),
        "scenario_time_limits": compute_scenario_time_limits_required(),
    }

    show_ai_generate_map = {
        r: scores.best.get(r) is not None for r in SIMULATION_RESOURCES
    }

    basic_show_ai_generate = any(
        show_ai_generate_map.get(r, False)
        for r in ("names", "descriptions", "flags", "departments", "scenarios")
    )

    suggestions_map: dict[str, list[UUID]] = {
        "names": [n.id for n in simulation.resources["names"].suggestions],
        "descriptions": [
            d.id for d in simulation.resources["descriptions"].suggestions
        ],
        "departments": [d.id for d in simulation.resources["departments"].suggestions],
        "scenarios": [s.id for s in simulation.resources["scenarios"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    # ── Step 7: Resource conversion + response assembly ───────────────────

    # Converters
    def _to_department(d) -> SimulationDepartment:
        return SimulationDepartment(
            department_id=d.id,
            name=d.name,
            description=d.description,
            generated=d.generated,
        )

    def _to_scenario(s) -> SimulationScenario:
        return SimulationScenario(
            scenario_id=s.id,
            name=s.name,
            description=s.description,
            generated=s.generated,
            **compute_scenario_show_flags(
                problem_statement_enabled=s.problem_statement_enabled,
                objectives_enabled=s.objectives_enabled,
                video_enabled=s.video_enabled,
                images_enabled=s.images_enabled,
                questions_enabled=s.questions_enabled,
            ),
        )

    # Build flag configs
    flags_available = simulation.resources["flags"].suggestions
    simulation_flags = [
        SimulationFlagConfig(
            key=flag.name,
            label=flag.name,
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            generated=flag.generated,
        )
        for flag in flags_available
        if flag.id
    ]

    flag_ids_set = {f.id for f in simulation.resources["flags"].selected}

    # Convert resources
    all_names = dedupe_by_id(
        simulation.resources["names"].selected
        + simulation.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        simulation.resources["descriptions"].selected
        + simulation.resources["descriptions"].suggestions
    )
    all_departments_conv = [_to_department(d) for d in all_departments]
    all_scenarios_conv = [_to_scenario(s) for s in all_scenarios]

    current_departments = [
        _to_department(d) for d in simulation.resources["departments"].selected
    ]
    current_scenarios = [
        _to_scenario(s) for s in simulation.resources["scenarios"].selected
    ]

    return GetSimulationApiResponse(
        # Context
        actor_name=profile.name,
        simulation_exists=simulation.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=simulation.draft_version,
        group_id=group_id,
        # Step-level AI generation flags
        basic_show_ai_generate=basic_show_ai_generate,
        # Per-resource sections
        names=SimulationNameSection(
            **_section("names"),
            resource=_serialize_model(simulation.resources["names"].selected[0])
            if simulation.resources["names"].selected
            else None,
            resources=_serialize_models(all_names),
        ),
        descriptions=SimulationDescriptionSection(
            **_section("descriptions"),
            resource=_serialize_model(simulation.resources["descriptions"].selected[0])
            if simulation.resources["descriptions"].selected
            else None,
            resources=_serialize_models(all_descriptions),
        ),
        flags=SimulationFlagSection(
            **_section("flags"),
            current=[f for f in simulation_flags if f.flag_option_id in flag_ids_set],
            resources=simulation_flags,
        ),
        departments=SimulationDepartmentSection(
            **_section("departments"),
            current=current_departments,
            resources=all_departments_conv,
        ),
        scenarios=SimulationScenarioSection(
            **_section("scenarios"),
            current=current_scenarios,
            resources=all_scenarios_conv,
        ),
        scenario_flags=SimulationScenarioFlagSection(
            **_section("scenario_flags"),
            current=_serialize_models(simulation.resources["scenario_flags"].selected),
            resources=_serialize_models(all_scenario_flags),
        ),
        scenario_positions=SimulationScenarioPositionSection(
            **_section("scenario_positions"),
            current=_serialize_models(
                simulation.resources["scenario_positions"].selected
            ),
            resources=_serialize_models(all_scenario_positions),
        ),
        scenario_rubrics=SimulationScenarioRubricSection(
            **_section("scenario_rubrics"),
            current=_serialize_models(
                simulation.resources["scenario_rubrics"].selected
            ),
            resources=_serialize_models(all_scenario_rubrics),
        ),
        scenario_time_limits=SimulationScenarioTimeLimitSection(
            **_section("scenario_time_limits"),
            current=_serialize_models(
                simulation.resources["scenario_time_limits"].selected
            ),
            resources=_serialize_models(all_scenario_time_limits),
        ),
        rubrics=_serialize_models(simulation.resources["rubrics"].suggestions),
    )
