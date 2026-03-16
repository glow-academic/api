"""Cohort permission functions - business logic extracted from SQL.

These functions compute permissions for cohort operations based on user role,
department membership, and cohort usage.
"""

from uuid import UUID

from app.infra.agent.selection import (
    select_agents_for_artifact,
    select_multi_resource_agent,
)
from app.infra.v5_types import CandidateAgent

# Re-export for backwards compatibility
__all__ = [
    "CandidateAgent",
    "select_agents_for_artifact",
    "select_multi_resource_agent",
    "COHORT_RESOURCES",
    "COHORT_BASIC_RESOURCES",
    "COHORT_PROFILES_RESOURCES",
    # Permission functions
    "compute_can_edit",
    "compute_disabled_reason",
    "has_access",
    # UI show flags
    "compute_show_name",
    "compute_show_description",
    "compute_show_flag",
    "compute_show_departments",
    "compute_show_simulations",
    "compute_show_simulation_positions",
    "compute_show_simulation_availability",
    "compute_show_profiles",
    "compute_show_profile_personas",
    # Required field flags
    "compute_name_required",
    "compute_description_required",
    "compute_flag_required",
    "compute_departments_required",
    "compute_simulations_required",
    "compute_simulation_positions_required",
    "compute_simulation_availability_required",
    "compute_profiles_required",
    "compute_profile_personas_required",
]

# ========== Agent Scoring - Cohort-specific Constants ==========

# Cohort-specific resource definitions (hardcoded, rarely changes)
COHORT_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
    "simulations",
    "profiles",
    "profile_personas",
}

# Multi-resource agent definitions for cohort
COHORT_BASIC_RESOURCES: set[str] = {"names", "descriptions", "flags", "departments"}
COHORT_SIMULATIONS_RESOURCES: set[str] = {
    "simulations",
    "simulation_positions",
    "simulation_availability",
}
COHORT_PROFILES_RESOURCES: set[str] = {"profiles", "profile_personas"}

# ========== Domain Metadata - for client-side display in modals ==========

COHORT_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "The cohort display name",
        "icon": "type",
    },
    "descriptions": {
        "name": "Description",
        "description": "A description of the cohort",
        "icon": "align-left",
    },
    "flags": {
        "name": "Status",
        "description": "Active/inactive status flag",
        "icon": "flag",
    },
    "departments": {
        "name": "Departments",
        "description": "Departments assigned to cohort",
        "icon": "building-2",
    },
    "simulations": {
        "name": "Simulations",
        "description": "Simulations included in cohort",
        "icon": "play-circle",
    },
    "simulation_positions": {
        "name": "Simulation Order",
        "description": "Order of simulations",
        "icon": "list-ordered",
    },
    "simulation_availability": {
        "name": "Simulation Availability",
        "description": "Availability windows for simulations",
        "icon": "calendar",
    },
    "profiles": {
        "name": "Profiles",
        "description": "Profiles assigned to cohort",
        "icon": "user",
    },
    "profile_personas": {
        "name": "Profile Personas",
        "description": "Persona assignments for profiles in cohort",
        "icon": "user-check",
    },
}


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
) -> list:
    """Build rich domain metadata for client display.

    Delegates to shared build_domain_data with cohort-specific metadata.
    """
    from app.infra.v5_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, COHORT_DOMAIN_METADATA
    )


# =============================================================================
# Core Permission Functions
# =============================================================================


def compute_can_edit(
    user_role: str | None,
    cohort_department_ids: list[str] | list[UUID] | None,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Not a default cohort (unless superadmin)
    2. User has admin/instructional/superadmin role
    3. Non-superadmins must belong to ALL of the cohort's departments
    """
    # Default cohorts can only be edited by superadmin
    if not cohort_department_ids and user_role != "superadmin":
        return False

    # Role check
    if user_role not in ("admin", "instructional", "superadmin"):
        return False

    # Department subset check (when user_department_ids is available)
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and cohort_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        cohort_dept_set = {str(d) for d in cohort_department_ids}
        if not cohort_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_can_delete(
    user_role: str | None,
    cohort_department_ids: list[str] | list[UUID] | None,
    usage_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default cohorts (no departments) cannot be deleted except by superadmin
    - Only admins, instructional, and superadmins can delete

    NOTE: usage_count (profile links) is intentionally NOT checked here.
    Unlike other artifacts where usage_count blocks deletion because child
    artifacts depend on the parent (e.g. can't delete a simulation used by
    cohorts), cohort->profile links are just assignments, not dependencies.
    Historical data (attempts, chats) is preserved separately in fact tables,
    so deleting a cohort doesn't lose any historical records.
    """
    if not cohort_department_ids and user_role != "superadmin":
        return False
    # if usage_count > 0:
    #     return False
    return user_role in ("admin", "instructional", "superadmin")


def compute_can_duplicate(user_role: str | None) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Only admin/instructional/superadmin can duplicate
    """
    return user_role in ("admin", "instructional", "superadmin")


def compute_can_leave(is_member: bool) -> bool:
    """Compute if user can leave the cohort.

    Rules:
    - User can leave if they are a member of the cohort
    """
    return is_member


def compute_disabled_reason(
    user_role: str | None,
    cohort_department_ids: list[str] | list[UUID] | None,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> str | None:
    """Compute the disabled reason for editing a cohort.

    Returns None if editing is allowed, otherwise returns a message.
    """
    # Default cohorts can only be edited by superadmin
    if not cohort_department_ids and user_role != "superadmin":
        return "This is a default cohort that cannot be edited."

    if user_role not in ("admin", "instructional", "superadmin"):
        return "This cohort cannot be edited."

    # Department subset check
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and cohort_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        cohort_dept_set = {str(d) for d in cohort_department_ids}
        if not cohort_dept_set.issubset(user_dept_set):
            return (
                "You don't have access to all departments for this cohort. "
                "You can view the details but cannot make changes."
            )

    return None


def has_access(
    user_role: str | None,
    user_department_ids: list[str] | list[UUID] | None,
    cohort_department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Check if user has access to view the cohort.

    Access rules:
    - Superadmin has access to all cohorts
    - User has access if cohort has no departments (default cohort)
    - User has access if they share at least one department with the cohort
    """
    if user_role == "superadmin":
        return True

    # Default cohorts (no departments) are accessible to all
    if not cohort_department_ids:
        return True

    # Check department overlap
    if not user_department_ids:
        return False

    user_dept_set = {str(d) for d in user_department_ids}
    cohort_dept_set = {str(d) for d in cohort_department_ids}
    return bool(user_dept_set & cohort_dept_set)


# =============================================================================
# UI Visibility Flags
# =============================================================================


def compute_show_name() -> bool:
    """Name is always shown."""
    return True


def compute_show_description() -> bool:
    """Description is always shown."""
    return True


def compute_show_flag() -> bool:
    """Flag (active status) is always shown."""
    return True


def compute_show_departments(departments_count: int) -> bool:
    """Show departments section if there are departments available."""
    return departments_count > 0


def compute_show_simulations(simulations_count: int) -> bool:
    """Show simulations section if there are simulations available."""
    return simulations_count > 0


def compute_show_simulation_positions(simulation_positions_count: int) -> bool:
    """Show simulation positions section if there are positions."""
    return simulation_positions_count > 0


def compute_show_simulation_availability(simulation_availability_count: int) -> bool:
    """Show simulation availability section if there are availability entries."""
    return simulation_availability_count > 0


def compute_show_profiles(profiles_count: int) -> bool:
    """Show profiles section if there are profiles available."""
    return profiles_count > 0


def compute_show_profile_personas(profile_personas_count: int) -> bool:
    """Show profile personas section if there are profile personas available."""
    return profile_personas_count > 0


# =============================================================================
# Required Field Flags
# =============================================================================


def compute_name_required() -> bool:
    """Name is always required."""
    return True


def compute_description_required() -> bool:
    """Description is optional."""
    return False


def compute_flag_required() -> bool:
    """Flag is optional."""
    return False


def compute_departments_required(show_departments: bool) -> bool:
    """Departments are required if the section is shown."""
    return show_departments


def compute_simulations_required() -> bool:
    """Simulations are optional."""
    return False


def compute_simulation_positions_required() -> bool:
    """Simulation positions are optional."""
    return False


def compute_simulation_availability_required() -> bool:
    """Simulation availability is optional."""
    return False


def compute_profiles_required() -> bool:
    """Profiles are optional."""
    return False


def compute_profile_personas_required() -> bool:
    """Profile personas are optional."""
    return False


# =============================================================================
# Validation Helpers
# =============================================================================


def get_missing_tools(
    names_has_tools: bool,
    departments_has_tools: bool,
    show_departments: bool,
) -> list[str]:
    """Get list of required resources that are missing tools.

    Returns list of resource names that need tools but don't have them.
    """
    missing: list[str] = []

    if not names_has_tools:
        missing.append("name")

    if show_departments and not departments_has_tools:
        missing.append("departments")

    return missing


# =============================================================================
# Save/Create Permissions
# =============================================================================


def compute_can_create(
    user_role: str | None,
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new cohort.

    Business logic:
    - Only admin/instructional/superadmin can create cohorts
    - Non-superadmins cannot create general objects (no departments)
    """
    if user_role not in ("admin", "instructional", "superadmin"):
        return False
    if user_role != "superadmin" and not department_ids:
        return False
    return True


def compute_can_draft(user_role: str | None) -> bool:
    """Compute permission to create or update a draft.

    Business logic:
    - Only admin/instructional/superadmin can create/edit drafts
    """
    return user_role in ("admin", "instructional", "superadmin")
