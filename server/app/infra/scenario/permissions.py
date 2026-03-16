"""Scenario permissions - Business logic for access control and permissions.

This module extracts permission computation from SQL into Python,
following the two-pass architecture pattern.
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
    "SCENARIO_RESOURCES",
    "SCENARIO_BASIC_RESOURCES",
    "SCENARIO_CONTENT_RESOURCES",
]

# ========== Agent Scoring - Scenario-specific Constants ==========

# Scenario-specific resource definitions
SCENARIO_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "problem_statements",
    "objectives",
    "flags",
    "images",
    "videos",
    "questions",
    "options",
    "departments",
    "fields",
    "personas",
    "documents",
}

# Multi-resource agent definitions for scenario
SCENARIO_BASIC_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
}

SCENARIO_CONTENT_RESOURCES: set[str] = {
    "personas",
    "documents",
    "parameters",
    "fields",
    "objectives",
    "images",
    "videos",
    "questions",
    "problem_statements",
}

# ========== Domain Metadata - for client-side display in modals ==========

SCENARIO_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "The display name for this scenario",
        "icon": "file-text",
    },
    "descriptions": {
        "name": "Description",
        "description": "A brief description of this scenario",
        "icon": "align-left",
    },
    "problem_statements": {
        "name": "Problem Statement",
        "description": "The problem statement for this scenario",
        "icon": "help-circle",
    },
    "flags": {
        "name": "Settings",
        "description": "Scenario settings and flags",
        "icon": "flag",
    },
    "departments": {
        "name": "Departments",
        "description": "Which departments can access this scenario",
        "icon": "building",
    },
    "personas": {
        "name": "Personas",
        "description": "AI personas used in this scenario",
        "icon": "user",
    },
    "documents": {
        "name": "Documents",
        "description": "Reference documents for this scenario",
        "icon": "file",
    },
    "parameters": {
        "name": "Parameters",
        "description": "Configuration parameters for this scenario",
        "icon": "settings",
    },
    "fields": {
        "name": "Fields",
        "description": "Custom fields for this scenario",
        "icon": "form-input",
    },
    "objectives": {
        "name": "Objectives",
        "description": "Learning objectives for this scenario",
        "icon": "target",
    },
    "images": {
        "name": "Images",
        "description": "Images used in this scenario",
        "icon": "image",
    },
    "videos": {
        "name": "Videos",
        "description": "Videos used in this scenario",
        "icon": "video",
    },
    "questions": {
        "name": "Questions",
        "description": "Assessment questions for this scenario",
        "icon": "message-square",
    },
}

# =============================================================================
# Access Control
# =============================================================================


def has_access(
    user_role: str | None,
    user_department_ids: list[UUID] | None,
    scenario_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to the scenario.

    Args:
        user_role: User's role (superadmin, admin, staff, learner)
        user_department_ids: List of department IDs user belongs to
        scenario_department_ids: List of department IDs scenario belongs to

    Returns:
        True if user has access to the scenario
    """
    # Superadmins have access to everything
    if user_role == "superadmin":
        return True

    # If scenario has no departments, it's accessible to all
    if not scenario_department_ids:
        return True

    # If user has no departments, they only get access to non-department scenarios
    if not user_department_ids:
        return False

    # Check if user shares any department with the scenario
    user_dept_set = set(user_department_ids)
    scenario_dept_set = set(scenario_department_ids)
    return bool(user_dept_set & scenario_dept_set)


# =============================================================================
# Edit Permissions
# =============================================================================


def compute_can_edit(
    user_role: str | None,
    scenario_department_ids: list[str] | list[UUID] | None,
    active_simulation_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Not a default scenario (unless superadmin)
    2. Not linked to active simulations
    3. User has admin/instructional/superadmin role
    4. Non-superadmins must belong to ALL of the scenario's departments
    """
    # Default scenarios can only be edited by superadmin
    if not scenario_department_ids and user_role != "superadmin":
        return False

    # Scenarios in use by simulations cannot be edited
    if active_simulation_count > 0:
        return False

    # Role check
    if user_role not in ("admin", "instructional", "superadmin"):
        return False

    # Department subset check (when user_department_ids is available)
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and scenario_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        scenario_dept_set = {str(d) for d in scenario_department_ids}
        if not scenario_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_disabled_reason(
    user_role: str | None,
    scenario_department_ids: list[str] | list[UUID] | None,
    active_simulation_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> str | None:
    """Compute reason why editing is disabled.

    Returns None if editing is allowed.
    """
    # Default scenarios can only be edited by superadmin
    if not scenario_department_ids and user_role != "superadmin":
        return (
            "This is a default scenario that cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Scenarios in use by simulations cannot be edited
    if active_simulation_count > 0:
        return (
            "This scenario is currently in use by simulations and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Role check
    if user_role not in ("admin", "instructional", "superadmin"):
        return (
            "This scenario cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Department subset check
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and scenario_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        scenario_dept_set = {str(d) for d in scenario_department_ids}
        if not scenario_dept_set.issubset(user_dept_set):
            return (
                "You don't have access to all departments for this scenario. "
                "You can view the details but cannot make changes."
            )

    return None


# =============================================================================
# List Permissions
# =============================================================================


def compute_can_delete(
    user_role: str | None,
    scenario_department_ids: list[str] | list[UUID] | None,
    active_simulation_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default scenarios (no departments) cannot be deleted except by superadmin
    - Scenarios linked to active simulations cannot be deleted
    - Only admins, instructional, and superadmins can delete
    """
    # Default scenarios can only be deleted by superadmin
    if not scenario_department_ids and user_role != "superadmin":
        return False

    # Scenarios with active simulation links cannot be deleted
    if active_simulation_count > 0:
        return False

    # Only admins, instructional, and superadmins can delete
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
    """Compute permission to create a new scenario.

    Business logic:
    - Only admin/instructional/superadmin can create scenarios
    - Non-superadmins cannot create general objects (no departments)
    """
    # Role check first
    if user_role not in ("admin", "instructional", "superadmin"):
        return False

    # Non-superadmins cannot create general objects (no departments)
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


def compute_show_name() -> bool:
    """Compute whether to show name field.

    Returns:
        Always True - name is always shown
    """
    return True


def compute_show_description() -> bool:
    """Compute whether to show description field.

    Returns:
        Always True - description is always shown
    """
    return True


def compute_show_flag() -> bool:
    """Compute whether to show flag field.

    Returns:
        Always True - flag is always shown
    """
    return True


def compute_show_departments(departments_count: int | None) -> bool:
    """Compute whether to show departments field.

    Args:
        departments_count: Number of available departments

    Returns:
        True if departments field should be shown
    """
    count = departments_count or 0
    return count > 0


def compute_show_personas(personas_count: int | None) -> bool:
    """Compute whether to show personas field.

    Args:
        personas_count: Number of available personas

    Returns:
        True if personas field should be shown
    """
    count = personas_count or 0
    return count > 0


def compute_show_objectives(objectives_count: int | None) -> bool:
    """Compute whether to show objectives field.

    Args:
        objectives_count: Number of available objectives

    Returns:
        True if objectives field should be shown
    """
    count = objectives_count or 0
    return count > 0


def compute_show_documents(documents_count: int | None) -> bool:
    """Compute whether to show documents field.

    Args:
        documents_count: Number of available documents

    Returns:
        True if documents field should be shown
    """
    count = documents_count or 0
    return count > 0


def compute_show_parameters(parameters_count: int | None) -> bool:
    """Compute whether to show parameters field.

    Args:
        parameters_count: Number of available parameters

    Returns:
        True if parameters field should be shown
    """
    count = parameters_count or 0
    return count > 0


def compute_show_fields(fields_count: int | None) -> bool:
    """Compute whether to show fields field.

    Args:
        fields_count: Number of available fields

    Returns:
        True if fields field should be shown
    """
    count = fields_count or 0
    return count > 0


def compute_show_images(images_count: int | None) -> bool:
    """Compute whether to show images field.

    Args:
        images_count: Number of available images

    Returns:
        True if images field should be shown
    """
    count = images_count or 0
    return count > 0


def compute_show_videos(videos_count: int | None) -> bool:
    """Compute whether to show videos field.

    Args:
        videos_count: Number of available videos

    Returns:
        True if videos field should be shown
    """
    count = videos_count or 0
    return count > 0


def compute_show_questions(questions_count: int | None) -> bool:
    """Compute whether to show questions field.

    Args:
        questions_count: Number of available questions

    Returns:
        True if questions field should be shown
    """
    count = questions_count or 0
    return count > 0


def compute_show_problem_statement() -> bool:
    """Compute whether to show problem statement field.

    Returns:
        Always True - problem statement is always shown
    """
    return True


# =============================================================================
# Required Flags
# =============================================================================


def compute_name_required() -> bool:
    """Compute whether name is required.

    Returns:
        Always True - name is always required
    """
    return True


def compute_description_required() -> bool:
    """Compute whether description is required.

    Returns:
        Always False - description is optional
    """
    return False


def compute_departments_required() -> bool:
    """Compute whether departments are required.

    Returns:
        Always False - departments are optional
    """
    return False


def compute_personas_required() -> bool:
    """Compute whether personas are required.

    Returns:
        Always True - at least one persona is required
    """
    return True


def compute_objectives_required() -> bool:
    """Compute whether objectives are required.

    Returns:
        Always False - objectives are optional
    """
    return False


def compute_documents_required() -> bool:
    """Compute whether documents are required.

    Returns:
        Always False - documents are optional
    """
    return False


def compute_parameters_required() -> bool:
    """Compute whether parameters are required.

    Returns:
        Always False - parameters are optional
    """
    return False


def compute_fields_required() -> bool:
    """Compute whether fields are required.

    Returns:
        Always False - fields are optional
    """
    return False


def compute_images_required() -> bool:
    """Compute whether images are required.

    Returns:
        Always False - images are optional
    """
    return False


def compute_videos_required() -> bool:
    """Compute whether videos are required.

    Returns:
        Always False - videos are optional
    """
    return False


def compute_questions_required() -> bool:
    """Compute whether questions are required.

    Returns:
        Always False - questions are optional
    """
    return False


def compute_problem_statement_required() -> bool:
    """Compute whether problem statement is required.

    Returns:
        Always False - problem statement is optional
    """
    return False


def compute_flag_required() -> bool:
    """Compute whether flag is required.

    Returns:
        Always False - flag is optional
    """
    return False


# =============================================================================
# Missing Tools Check
# =============================================================================


def get_missing_tools(
    names_has_tools: bool | None,
    descriptions_has_tools: bool | None,
    flags_has_tools: bool | None,
    departments_has_tools: bool | None,
    personas_has_tools: bool | None,
    objectives_has_tools: bool | None = None,
    documents_has_tools: bool | None = None,
    parameters_has_tools: bool | None = None,
    fields_has_tools: bool | None = None,
    images_has_tools: bool | None = None,
    videos_has_tools: bool | None = None,
    questions_has_tools: bool | None = None,
    problem_statements_has_tools: bool | None = None,
) -> list[str]:
    """Get list of missing tools.

    Args:
        names_has_tools: Whether names tools exist
        descriptions_has_tools: Whether descriptions tools exist
        flags_has_tools: Whether flags tools exist
        departments_has_tools: Whether departments tools exist
        personas_has_tools: Whether personas tools exist
        objectives_has_tools: Whether objectives tools exist
        documents_has_tools: Whether documents tools exist
        parameters_has_tools: Whether parameters tools exist
        fields_has_tools: Whether fields tools exist
        images_has_tools: Whether images tools exist
        videos_has_tools: Whether videos tools exist
        questions_has_tools: Whether questions tools exist
        problem_statements_has_tools: Whether problem statements tools exist

    Returns:
        List of missing tool names
    """
    missing = []

    if not names_has_tools:
        missing.append("names")
    if not descriptions_has_tools:
        missing.append("descriptions")
    if not flags_has_tools:
        missing.append("flags")
    if not departments_has_tools:
        missing.append("departments")
    if not personas_has_tools:
        missing.append("personas")
    if objectives_has_tools is False:
        missing.append("objectives")
    if documents_has_tools is False:
        missing.append("documents")
    if parameters_has_tools is False:
        missing.append("parameters")
    if fields_has_tools is False:
        missing.append("fields")
    if images_has_tools is False:
        missing.append("images")
    if videos_has_tools is False:
        missing.append("videos")
    if questions_has_tools is False:
        missing.append("questions")
    if problem_statements_has_tools is False:
        missing.append("problem_statements")

    return missing
