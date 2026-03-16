"""Canonical cohort section assembly."""

from __future__ import annotations

from uuid import UUID

from app.infra.cohort.permissions import (
    COHORT_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_profile_personas_required,
    compute_profiles_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_profile_personas,
    compute_show_profiles,
    compute_show_simulation_availability,
    compute_show_simulation_positions,
    compute_show_simulations,
    compute_simulation_availability_required,
    compute_simulation_positions_required,
    compute_simulations_required,
)
from app.infra.cohort.permissions_context import CohortPermissionsContext
from app.infra.common_context import CommonContext
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import ArtifactToolScores
from app.infra.types import ArtifactContext
from app.infra.cohort.types import (
    CohortDepartment,
    CohortDepartmentSection,
    CohortDescriptionResource,
    CohortDescriptionSection,
    CohortFlagConfig,
    CohortFlagSection,
    CohortNameResource,
    CohortNameSection,
    CohortProfile,
    CohortProfilePersona,
    CohortProfilePersonaSection,
    CohortProfileSection,
    CohortSimulation,
    CohortSimulationAvailability,
    CohortSimulationAvailabilitySection,
    CohortSimulationPosition,
    CohortSimulationPositionSection,
    CohortSimulationSection,
    GetCohortApiResponse,
)


def build_cohort_get_result(
    *,
    common: CommonContext,
    cohort: ArtifactContext,
    scores: ArtifactToolScores,
    perms: CohortPermissionsContext | None,
    cohort_id: UUID | None,
    group_id: UUID | None,
) -> GetCohortApiResponse:
    """Build the canonical cohort response bundle from resolved contexts."""
    profile = common.profile
    tool_ids_map: dict[str, UUID | None] = {
        resource: (scores.best[resource].tool_id if scores.best.get(resource) else None)
        for resource in COHORT_RESOURCES
    }

    cohort_department_ids = [
        department.id
        for department in cohort.resources["departments"].selected
        if department.id
    ]
    can_edit = compute_can_edit(
        user_role=profile.role,
        cohort_department_ids=cohort_department_ids,
        user_department_ids=profile.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        cohort_department_ids=cohort_department_ids,
        user_department_ids=profile.department_ids,
    )

    all_departments = dedupe_by_id(
        cohort.resources["departments"].selected
        + cohort.resources["departments"].suggestions
    )
    all_simulations = dedupe_by_id(
        cohort.resources["simulations"].selected
        + cohort.resources["simulations"].suggestions
    )
    all_profiles = dedupe_by_id(
        cohort.resources["profiles"].selected + cohort.resources["profiles"].suggestions
    )
    all_simulation_positions = cohort.resources["simulation_positions"].selected
    all_simulation_availability = cohort.resources["simulation_availability"].selected
    all_profile_personas = cohort.resources["profile_personas"].selected

    if cohort_id is None and not all_departments:
        raise ValueError("No accessible departments found for user")

    show_departments_flag = compute_show_departments(len(all_departments))
    show_flags_map = {
        "names": compute_show_name(),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "departments": show_departments_flag,
        "simulations": compute_show_simulations(len(all_simulations)),
        "simulation_positions": compute_show_simulation_positions(
            len(all_simulation_positions)
        ),
        "simulation_availability": compute_show_simulation_availability(
            len(all_simulation_availability)
        ),
        "profiles": compute_show_profiles(len(all_profiles)),
        "profile_personas": compute_show_profile_personas(len(all_profile_personas)),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(show_departments_flag),
        "simulations": compute_simulations_required(),
        "simulation_positions": compute_simulation_positions_required(),
        "simulation_availability": compute_simulation_availability_required(),
        "profiles": compute_profiles_required(),
        "profile_personas": compute_profile_personas_required(),
    }
    show_ai_generate_map = {
        resource: scores.best.get(resource) is not None for resource in COHORT_RESOURCES
    }
    basic_show_ai_generate = any(
        show_ai_generate_map.get(resource, False)
        for resource in ("names", "descriptions", "flags", "departments")
    )
    simulations_step_show_ai_generate = any(
        show_ai_generate_map.get(resource, False)
        for resource in (
            "simulations",
            "simulation_positions",
            "simulation_availability",
        )
    )
    profiles_step_show_ai_generate = any(
        show_ai_generate_map.get(resource, False)
        for resource in ("profiles", "profile_personas")
    )

    suggestions_map: dict[str, list[UUID]] = {
        "names": [item.id for item in cohort.resources["names"].suggestions],
        "descriptions": [
            item.id for item in cohort.resources["descriptions"].suggestions
        ],
        "departments": [
            item.id for item in cohort.resources["departments"].suggestions
        ],
        "simulations": [
            item.id for item in cohort.resources["simulations"].suggestions if item.id
        ],
        "profiles": [
            item.id for item in cohort.resources["profiles"].suggestions if item.id
        ],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    def _to_department(item) -> CohortDepartment:
        return CohortDepartment(
            department_id=item.id,
            name=item.name,
            description=item.description,
            generated=item.generated,
        )

    def _to_name(item) -> CohortNameResource:
        return CohortNameResource(
            id=item.id,
            name=item.name,
            generated=item.generated,
        )

    def _to_description(item) -> CohortDescriptionResource:
        return CohortDescriptionResource(
            id=item.id,
            description=item.description,
            generated=item.generated,
        )

    def _to_simulation(item) -> CohortSimulation:
        return CohortSimulation(
            simulation_id=item.id,
            name=item.name,
            description=item.description,
            generated=item.generated,
        )

    def _to_profile(item) -> CohortProfile:
        return CohortProfile(
            profile_id=item.id,
            name=item.name,
            description=item.description,
        )

    def _to_simulation_position(item) -> CohortSimulationPosition:
        return CohortSimulationPosition(
            simulation_id=item.simulation_id,
            value=item.value,
            generated=item.generated,
            mcp=item.mcp,
        )

    def _to_simulation_availability(item) -> CohortSimulationAvailability:
        return CohortSimulationAvailability(
            id=item.id,
            simulation_id=item.simulation_id,
            time=item.time,
            type=item.type,
            generated=item.generated,
            mcp=item.mcp,
        )

    def _to_profile_persona(item) -> CohortProfilePersona:
        return CohortProfilePersona(
            id=item.id,
            profile_id=item.profile_id,
            persona_id=item.persona_id,
            generated=item.generated,
        )

    all_flags = (
        cohort.resources["flags"].selected + cohort.resources["flags"].suggestions
    )
    flag_configs = [
        CohortFlagConfig(
            key=flag.name,
            label=flag.name,
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            generated=flag.generated,
        )
        for flag in all_flags
        if flag.id
    ]
    flag_ids_set = {flag.id for flag in cohort.resources["flags"].selected}

    all_names = dedupe_by_id(
        cohort.resources["names"].selected + cohort.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        cohort.resources["descriptions"].selected
        + cohort.resources["descriptions"].suggestions
    )
    all_names_conv = [_to_name(item) for item in all_names]
    all_descriptions_conv = [_to_description(item) for item in all_descriptions]
    all_departments_conv = [_to_department(item) for item in all_departments]
    all_simulations_conv = [_to_simulation(item) for item in all_simulations]
    all_profiles_conv = [_to_profile(item) for item in all_profiles]
    all_sim_positions_conv = [
        _to_simulation_position(item) for item in all_simulation_positions
    ]
    all_sim_availability_conv = [
        _to_simulation_availability(item) for item in all_simulation_availability
    ]
    all_profile_personas_conv = [
        _to_profile_persona(item) for item in all_profile_personas
    ]

    current_departments = [
        _to_department(item) for item in cohort.resources["departments"].selected
    ]
    current_simulations = [
        _to_simulation(item) for item in cohort.resources["simulations"].selected
    ]
    current_profiles = [
        _to_profile(item) for item in cohort.resources["profiles"].selected
    ]

    return GetCohortApiResponse(
        actor_name=profile.name,
        cohort_exists=cohort.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=cohort.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        simulations_step_show_ai_generate=simulations_step_show_ai_generate,
        profiles_step_show_ai_generate=profiles_step_show_ai_generate,
        names=CohortNameSection(
            **_section("names"),
            resource=_to_name(cohort.resources["names"].selected[0])
            if cohort.resources["names"].selected
            else None,
            resources=all_names_conv,
        ),
        descriptions=CohortDescriptionSection(
            **_section("descriptions"),
            resource=_to_description(cohort.resources["descriptions"].selected[0])
            if cohort.resources["descriptions"].selected
            else None,
            resources=all_descriptions_conv,
        ),
        flags=CohortFlagSection(
            **_section("flags"),
            resource=next(
                (flag for flag in flag_configs if flag.flag_option_id in flag_ids_set),
                None,
            ),
            resources=flag_configs,
        ),
        departments=CohortDepartmentSection(
            **_section("departments"),
            current=current_departments,
            resources=all_departments_conv,
        ),
        simulations=CohortSimulationSection(
            **_section("simulations"),
            current=current_simulations,
            resources=all_simulations_conv,
        ),
        simulation_positions=CohortSimulationPositionSection(
            **_section("simulation_positions"),
            current=all_sim_positions_conv,
            resources=all_sim_positions_conv,
        ),
        simulation_availability=CohortSimulationAvailabilitySection(
            **_section("simulation_availability"),
            current=all_sim_availability_conv,
            resources=all_sim_availability_conv,
        ),
        profiles=CohortProfileSection(
            **_section("profiles"),
            current=current_profiles,
            resources=all_profiles_conv,
        ),
        profile_personas=CohortProfilePersonaSection(
            **_section("profile_personas"),
            current=all_profile_personas_conv,
            resources=all_profile_personas_conv,
        ),
        personas=cohort.resources["personas"].suggestions,
    )
