"""Simulation permissions - Business logic for access control and permissions.

This module extracts permission computation from SQL into Python,
following the two-pass architecture pattern.
"""

from uuid import UUID

from app.infra.agent.selection import select_agents_for_artifact
from app.infra.v5_types import CandidateAgent

# Re-export for use in get.py
__all__ = [
    "CandidateAgent",
    "select_agents_for_artifact",
    "SIMULATION_RESOURCES",
]

# Simulation-specific resource definitions
SIMULATION_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
    "scenarios",
    "scenario_flags",
    "scenario_positions",
    "scenario_rubrics",
    "scenario_time_limits",
}

# =============================================================================
# Access Control
# =============================================================================


def has_access(
    user_role: str | None,
    user_department_ids: list[UUID] | None,
    simulation_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to the simulation."""
    if user_role == "superadmin":
        return True
    if not simulation_department_ids:
        return True
    if not user_department_ids:
        return False
    user_dept_set = set(user_department_ids)
    sim_dept_set = set(simulation_department_ids)
    return bool(user_dept_set & sim_dept_set)


# =============================================================================
# Edit Permissions
# =============================================================================


def compute_can_edit(
    user_role: str | None,
    simulation_department_ids: list[str] | list[UUID] | None,
    cohort_usage_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Not a default simulation (unless superadmin)
    2. Not linked to cohorts
    3. User has admin/instructional/superadmin role
    4. Non-superadmins must belong to ALL of the simulation's departments
    """
    # Default simulations can only be edited by superadmin
    if not simulation_department_ids and user_role != "superadmin":
        return False

    # Simulations in use by cohorts cannot be edited
    if cohort_usage_count > 0:
        return False

    # Role check
    if user_role not in ("admin", "instructional", "superadmin"):
        return False

    # Department subset check (when user_department_ids is available)
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and simulation_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        sim_dept_set = {str(d) for d in simulation_department_ids}
        if not sim_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_disabled_reason(
    user_role: str | None,
    simulation_department_ids: list[str] | list[UUID] | None,
    cohort_usage_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> str | None:
    """Compute reason why editing is disabled."""
    # Default simulations can only be edited by superadmin
    if not simulation_department_ids and user_role != "superadmin":
        return (
            "This is a default simulation that cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Simulations in use by cohorts cannot be edited
    if cohort_usage_count > 0:
        return (
            "This simulation is currently in use by cohorts and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Role check
    if user_role not in ("admin", "instructional", "superadmin"):
        return (
            "This simulation cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Department subset check
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and simulation_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        sim_dept_set = {str(d) for d in simulation_department_ids}
        if not sim_dept_set.issubset(user_dept_set):
            return (
                "You don't have access to all departments for this simulation. "
                "You can view the details but cannot make changes."
            )

    return None


# =============================================================================
# List Permissions
# =============================================================================


def compute_can_delete(
    user_role: str | None,
    simulation_department_ids: list[str] | list[UUID] | None,
    cohort_usage_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default simulations (no departments) cannot be deleted except by superadmin
    - Simulations linked to ANY cohort cannot be deleted
    - Only admins, instructional, and superadmins can delete
    """
    if not simulation_department_ids and user_role != "superadmin":
        return False
    if cohort_usage_count > 0:
        return False
    return user_role in ("admin", "instructional", "superadmin")


def compute_can_duplicate(user_role: str | None) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Only admin/instructional/superadmin can duplicate
    """
    return user_role in ("admin", "instructional", "superadmin")


# =============================================================================
# Save/Create Permissions
# =============================================================================


def compute_can_create(
    user_role: str | None,
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new simulation.

    Business logic:
    - Only admin/instructional/superadmin can create simulations
    - Non-superadmins cannot create general objects (no departments)
    """
    if user_role not in ("admin", "instructional", "superadmin"):
        return False
    if user_role != "superadmin" and not department_ids:
        return False
    return True


# =============================================================================
# Draft Permissions
# =============================================================================


def compute_can_draft(user_role: str | None) -> bool:
    """Compute permission to create or update a draft.

    Business logic:
    - Only admin/instructional/superadmin can create/edit drafts
    """
    return user_role in ("admin", "instructional", "superadmin")


# =============================================================================
# UI Show Flags
# =============================================================================


def compute_show_name(names_has_tools: bool | None) -> bool:
    """Compute whether to show name field."""
    return names_has_tools is True


def compute_show_description() -> bool:
    """Compute whether to show description field."""
    return True


def compute_show_departments(departments_count: int | None) -> bool:
    """Compute whether to show departments field."""
    count = departments_count or 0
    return count > 0


def compute_show_flag() -> bool:
    """Compute whether to show flag field."""
    return True


def compute_show_scenarios(scenarios_count: int | None) -> bool:
    """Compute whether to show scenarios field."""
    count = scenarios_count or 0
    return count > 0


def compute_show_scenario_flags(
    effective_scenario_ids: list[UUID] | None,
    scenario_flags_count: int,
    scenarios_count: int,
) -> bool:
    """Compute whether to show scenario flags."""
    return bool(
        effective_scenario_ids or scenario_flags_count > 0 or scenarios_count > 0
    )


def compute_show_scenario_positions(
    effective_scenario_ids: list[UUID] | None,
    scenario_positions_count: int,
    scenarios_count: int,
) -> bool:
    """Compute whether to show scenario positions."""
    return bool(
        effective_scenario_ids or scenario_positions_count > 0 or scenarios_count > 0
    )


def compute_show_scenario_rubrics(
    effective_scenario_ids: list[UUID] | None,
    scenario_rubrics_count: int,
    scenarios_count: int,
) -> bool:
    """Compute whether to show scenario rubrics."""
    return bool(
        effective_scenario_ids or scenario_rubrics_count > 0 or scenarios_count > 0
    )


def compute_show_scenario_time_limits(
    effective_scenario_ids: list[UUID] | None,
    scenario_time_limits_count: int,
    scenarios_count: int,
) -> bool:
    """Compute whether to show scenario time limits."""
    return bool(
        effective_scenario_ids or scenario_time_limits_count > 0 or scenarios_count > 0
    )


# =============================================================================
# Required Flags
# =============================================================================


def compute_name_required() -> bool:
    """Name is always required."""
    return True


def compute_description_required() -> bool:
    """Description is optional."""
    return False


def compute_departments_required() -> bool:
    """Departments are optional."""
    return False


def compute_flag_required() -> bool:
    """Flag is optional."""
    return False


def compute_scenarios_required() -> bool:
    """At least one scenario is needed."""
    return True


def compute_scenario_flags_required() -> bool:
    """Scenario flags are optional."""
    return False


def compute_scenario_positions_required() -> bool:
    """Scenario positions are optional."""
    return False


def compute_scenario_rubrics_required() -> bool:
    """Scenario rubrics are required."""
    return True


def compute_scenario_time_limits_required() -> bool:
    """Scenario time limits are optional."""
    return False


# =============================================================================
# Scenario Show Flags (per-scenario visibility)
# =============================================================================


def compute_scenario_show_flags(
    problem_statement_enabled: bool | None,
    objectives_enabled: bool | None,
    video_enabled: bool | None,
    images_enabled: bool | None,
    questions_enabled: bool | None,
) -> dict[str, bool]:
    """Compute show flags for scenario-level flag filtering."""
    ps_enabled = (
        problem_statement_enabled if problem_statement_enabled is not None else True
    )
    obj_enabled = objectives_enabled if objectives_enabled is not None else True
    vid_enabled = video_enabled if video_enabled is not None else False
    img_enabled = images_enabled if images_enabled is not None else False
    q_enabled = questions_enabled if questions_enabled is not None else False

    return {
        "show_problem_statement": ps_enabled,
        "show_objectives": obj_enabled,
        "show_video": vid_enabled,
        "show_text": not vid_enabled,
        "show_audio": not vid_enabled,
        "show_copy_paste": not vid_enabled,
        "show_images": img_enabled,
        "show_questions": q_enabled,
    }


# =============================================================================
# Domain Metadata - for client-side display in modals
# =============================================================================

SIMULATION_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "The display name for this simulation",
        "icon": "type",
    },
    "descriptions": {
        "name": "Description",
        "description": "A brief description of this simulation",
        "icon": "file-text",
    },
    "flags": {
        "name": "Status",
        "description": "Active/inactive and practice mode settings",
        "icon": "flag",
    },
    "departments": {
        "name": "Departments",
        "description": "Which departments can access this simulation",
        "icon": "building",
    },
    "scenarios": {
        "name": "Scenarios",
        "description": "Scenarios included in this simulation",
        "icon": "layout",
    },
    "scenario_flags": {
        "name": "Scenario Flags",
        "description": "Flag configurations for scenarios",
        "icon": "toggle-left",
    },
    "scenario_positions": {
        "name": "Scenario Positions",
        "description": "Position ordering for scenarios",
        "icon": "list-ordered",
    },
    "scenario_rubrics": {
        "name": "Scenario Rubrics",
        "description": "Rubric assignments for scenarios",
        "icon": "clipboard-check",
    },
    "scenario_time_limits": {
        "name": "Scenario Time Limits",
        "description": "Time limit settings for scenarios",
        "icon": "clock",
    },
}


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
) -> list:
    """Build rich domain metadata for client display."""
    from app.infra.v5_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, SIMULATION_DOMAIN_METADATA
    )


# =============================================================================
# Missing Tools Check
# =============================================================================


def get_missing_tools(
    names_has_tools: bool | None,
    descriptions_has_tools: bool | None,
    flags_has_tools: bool | None,
    departments_has_tools: bool | None,
    scenarios_has_tools: bool | None,
) -> list[str]:
    """Get list of missing tools."""
    missing = []
    if not names_has_tools:
        missing.append("names")
    if not descriptions_has_tools:
        missing.append("descriptions")
    if not flags_has_tools:
        missing.append("flags")
    if not departments_has_tools:
        missing.append("departments")
    if not scenarios_has_tools:
        missing.append("scenarios")
    return missing
