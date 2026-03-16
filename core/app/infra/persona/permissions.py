"""Persona permission helpers.

Extracts business logic from SQL into Python for the two-pass architecture.
These functions compute permissions, UI flags, and access control based on
data fetched from the Pass 1 SQL query.
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
    "PERSONA_RESOURCES",
    "PERSONA_BASIC_RESOURCES",
    "PERSONA_CONTENT_RESOURCES",
    "PERSONA_PARAMETERS_RESOURCES",
    "PERSONA_GENERAL_RESOURCES",
]


def compute_can_edit(
    user_role: str | None,
    persona_department_ids: list[str] | list[UUID] | None,
    active_scenario_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Not a default persona (unless superadmin)
    2. Not linked to active scenarios
    3. User has admin/instructional/superadmin role
    4. Non-superadmins must belong to ALL of the persona's departments
    """
    # Default personas can only be edited by superadmin
    if not persona_department_ids and user_role != "superadmin":
        return False

    # Personas in use by scenarios cannot be edited
    if active_scenario_count > 0:
        return False

    # Role check
    if user_role not in ("admin", "instructional", "superadmin"):
        return False

    # Department subset check (when user_department_ids is available)
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and persona_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        persona_dept_set = {str(d) for d in persona_department_ids}
        if not persona_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_disabled_reason(
    user_role: str | None,
    persona_department_ids: list[str] | list[UUID] | None,
    active_scenario_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    # Default personas can only be edited by superadmin
    if not persona_department_ids and user_role != "superadmin":
        return (
            "This is a default persona that cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Personas in use by scenarios cannot be edited
    if active_scenario_count > 0:
        return (
            "This persona is currently in use by scenarios and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Role check
    if user_role not in ("admin", "instructional", "superadmin"):
        return (
            "This persona cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Department subset check
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and persona_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        persona_dept_set = {str(d) for d in persona_department_ids}
        if not persona_dept_set.issubset(user_dept_set):
            return (
                "You don't have access to all departments for this persona. "
                "You can view the details but cannot make changes."
            )

    return None


def get_missing_tools(
    names_has_tools: bool,
    colors_has_tools: bool,
    icons_has_tools: bool,
    instructions_has_tools: bool,
    show_departments: bool,
    departments_has_tools: bool,
    show_parameter_fields: bool,
    parameter_fields_has_tools: bool,
    show_examples: bool,
    examples_has_tools: bool,
) -> list[str]:
    """Get list of missing required tools."""
    missing = []

    if not names_has_tools:
        missing.append("name")
    if not colors_has_tools:
        missing.append("color")
    if not icons_has_tools:
        missing.append("icon")
    if not instructions_has_tools:
        missing.append("instructions")
    if show_departments and not departments_has_tools:
        missing.append("departments")
    if show_parameter_fields and not parameter_fields_has_tools:
        missing.append("parameter_fields")
    if show_examples and not examples_has_tools:
        missing.append("examples")

    return missing


def has_access(
    user_role: str | None,
    user_department_ids: list[UUID] | None,
    persona_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the persona.

    Access rules:
    - Superadmin has access to all personas
    - User has access if persona has no departments (default persona)
    - User has access if they share at least one department with the persona
    """
    if user_role == "superadmin":
        return True

    # Default personas (no departments) are accessible to all
    if not persona_department_ids:
        return True

    # Check department overlap
    if not user_department_ids:
        return False

    user_dept_set = set(user_department_ids)
    persona_dept_set = set(persona_department_ids)
    return bool(user_dept_set & persona_dept_set)


def compute_show_name(names_has_tools: bool) -> bool:
    """Determine if name picker should be shown."""
    return True


def compute_show_description() -> bool:
    """Determine if description picker should be shown."""
    # Always show description picker
    return True


def compute_show_color(colors_has_tools: bool, colors_count: int) -> bool:
    """Determine if color picker should be shown."""
    return colors_count > 0


def compute_show_icon(icons_has_tools: bool, icons_count: int) -> bool:
    """Determine if icon picker should be shown."""
    return icons_count > 0


def compute_show_instructions(instructions_has_tools: bool) -> bool:
    """Determine if instructions picker should be shown."""
    return True


def compute_show_flag() -> bool:
    """Determine if flag toggle should be shown."""
    # Flag is always shown
    return True


def compute_show_departments(departments_count: int) -> bool:
    """Determine if departments picker should be shown."""
    return departments_count > 0


def compute_show_parameter_fields(parameter_fields_count: int) -> bool:
    """Determine if parameter_fields picker should be shown."""
    return parameter_fields_count > 0


def compute_show_examples(examples_count: int) -> bool:
    """Determine if examples editor should be shown."""
    # Show examples if there are any existing examples or suggestions
    return examples_count > 0


def compute_show_parameters(parameters_count: int) -> bool:
    """Determine if parameters picker should be shown."""
    return parameters_count > 0


def compute_name_required() -> bool:
    """Determine if name is required."""
    return True


def compute_description_required() -> bool:
    """Determine if description is required."""
    return False


def compute_color_required() -> bool:
    """Determine if color is required."""
    return True


def compute_icon_required() -> bool:
    """Determine if icon is required."""
    return True


def compute_instructions_required() -> bool:
    """Determine if instructions is required."""
    return True


def compute_flag_required() -> bool:
    """Determine if flag is required."""
    return False


def compute_departments_required() -> bool:
    """Determine if departments is required."""
    return False


def compute_parameter_fields_required() -> bool:
    """Determine if parameter_fields is required."""
    return False


def compute_examples_required() -> bool:
    """Determine if examples is required."""
    return False


def compute_parameters_required() -> bool:
    """Determine if parameters is required."""
    return False


def compute_show_voices(voices_count: int) -> bool:
    """Determine if voices picker should be shown."""
    return voices_count > 0


def compute_voices_required() -> bool:
    """Determine if voices is required."""
    return False


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    user_role: str | None,
    persona_department_ids: list[str] | list[UUID] | None,
    active_scenario_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default personas (no departments) cannot be deleted except by superadmin
    - Personas linked to active scenarios cannot be deleted
    - Only admins, instructional, and superadmins can delete
    """
    # Default personas can only be deleted by superadmin
    if not persona_department_ids and user_role != "superadmin":
        return False

    # Personas with active scenario links cannot be deleted
    if active_scenario_count > 0:
        return False

    # Only admins, instructional, and superadmins can delete
    return user_role in ("admin", "instructional", "superadmin")


def compute_can_duplicate(user_role: str | None) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Anyone with edit permissions can duplicate
    - Currently always true for admin/instructional/superadmin
    """
    return user_role in ("admin", "instructional", "superadmin")


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    user_role: str | None,
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new persona.

    Business logic (from SQL validate_department_create_permissions):
    - Non-superadmins cannot create general objects (empty department_ids)
    - Only admin/instructional/superadmin can create personas
    """
    # Role check first
    if user_role not in ("admin", "instructional", "superadmin"):
        return False

    # Non-superadmins cannot create general objects (no departments)
    if user_role != "superadmin" and not department_ids:
        return False

    return True


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(user_role: str | None) -> bool:
    """Compute permission to create or update a draft.

    Business logic:
    - Only admin/instructional/superadmin can create/edit drafts
    """
    return user_role in ("admin", "instructional", "superadmin")


# ========== Agent Scoring - Persona-specific Constants ==========

# Persona-specific resource definitions (hardcoded, rarely changes)
PERSONA_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "colors",
    "icons",
    "instructions",
    "flags",
    "departments",
    "parameter_fields",
    "examples",
    "voices",
}

# Multi-resource agent definitions for persona
PERSONA_BASIC_RESOURCES: set[str] = {"names", "descriptions", "flags", "departments"}
PERSONA_CONTENT_RESOURCES: set[str] = {"instructions", "examples", "voices"}
PERSONA_PARAMETERS_RESOURCES: set[str] = {"parameter_fields"}
PERSONA_GENERAL_RESOURCES: set[str] = PERSONA_RESOURCES  # All resources

# ========== Business Logic Helpers ==========


def compute_show_ai_generate(agent_ids: dict[str, UUID | None], resource: str) -> bool:
    """Returns True if an agent exists for that resource."""
    return agent_ids.get(resource) is not None


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'persona_active' -> ('active', 'Active')"""
    if not name:
        return ("unknown", "Unknown")
    # Remove artifact prefix (e.g., 'persona_active' -> 'active')
    key = name.replace("persona_", "")
    # Title case for label
    label = key.replace("_", " ").title()
    return (key, label)
