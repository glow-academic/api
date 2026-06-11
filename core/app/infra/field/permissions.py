"""Field permission helpers.

Extracts business logic from SQL into Python for the two-pass architecture.
These functions compute permissions, UI flags, and access control based on
data fetched from the Pass 1 SQL query.

Fully generic — no knowledge of specific role names.
All checks use two mechanisms:
  1. Permission set: (artifact, operation) tuples from role's permission_ids
  2. Role level: integer hierarchy (0 = highest privilege)
"""

from uuid import UUID

from app.infra.agent.selection import (
    select_agents_for_artifact,
    select_multi_resource_agent,
)
from app.infra.api_types import CandidateAgent
from app.infra.permissions_helpers import has_permission

# Re-export for backwards compatibility
__all__ = [
    "CandidateAgent",
    "select_agents_for_artifact",
    "select_multi_resource_agent",
    "FIELD_RESOURCES",
    "FIELD_BASIC_RESOURCES",
    "FIELD_GENERAL_RESOURCES",
]


def compute_can_edit(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    field_department_ids: list[str] | list[UUID] | None,
    active_parameter_count: int = 0,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Not a default field (unless level 0)
    2. Not linked to active parameters
    3. User has field:update permission
    4. Non-level-0 users must belong to ALL of the field's departments
    """
    # Default fields can only be edited by level 0
    if not field_department_ids and role_level > 0:
        return False

    # Fields in use by active parameters cannot be edited
    if active_parameter_count > 0:
        return False

    # Permission check
    if not has_permission(role_permissions, "field", "update"):
        return False

    # Department subset check (when user_department_ids is available)
    if (
        user_department_ids is not None
        and role_level > 0
        and field_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        field_dept_set = {str(d) for d in field_department_ids}
        if not field_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_disabled_reason(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    field_department_ids: list[str] | list[UUID] | None,
    active_parameter_count: int = 0,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    # Default fields can only be edited by level 0
    if not field_department_ids and role_level > 0:
        return (
            "This is a default field that cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Fields in use by active parameters cannot be edited
    if active_parameter_count > 0:
        return (
            "This field is currently in use by parameters and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Permission check
    if not has_permission(role_permissions, "field", "update"):
        return (
            "This field cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Department subset check
    if (
        user_department_ids is not None
        and role_level > 0
        and field_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        field_dept_set = {str(d) for d in field_department_ids}
        if not field_dept_set.issubset(user_dept_set):
            return (
                "You don't have access to all departments for this field. "
                "You can view the details but cannot make changes."
            )

    return None


def has_access(
    role_level: int,
    user_department_ids: list[UUID] | None,
    field_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the field.

    Access rules:
    - Level 0 (top-level) has access to all fields
    - User has access if field has no departments (default field)
    - User has access if they share at least one department with the field
    """
    if role_level == 0:
        return True

    # Default fields (no departments) are accessible to all
    if not field_department_ids:
        return True

    # Check department overlap
    if not user_department_ids:
        return False

    user_dept_set = set(user_department_ids)
    field_dept_set = set(field_department_ids)
    return bool(user_dept_set & field_dept_set)


def compute_show_name(names_has_tools: bool) -> bool:
    """Determine if name picker should be shown."""
    return names_has_tools


def compute_show_description() -> bool:
    """Determine if description picker should be shown."""
    return True


def compute_show_flag() -> bool:
    """Determine if flag toggle should be shown."""
    return True


def compute_show_departments(departments_count: int) -> bool:
    """Determine if departments picker should be shown."""
    return departments_count > 0


def compute_show_conditional_parameters(conditional_parameters_count: int) -> bool:
    """Determine if conditional parameters picker should be shown."""
    return conditional_parameters_count > 0


def compute_name_required() -> bool:
    """Determine if name is required."""
    return True


def compute_description_required() -> bool:
    """Determine if description is required."""
    return False


def compute_flag_required() -> bool:
    """Determine if flag is required."""
    return False


def compute_departments_required() -> bool:
    """Determine if departments is required."""
    return False


def compute_conditional_parameters_required() -> bool:
    """Determine if conditional parameters is required."""
    return False


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    field_department_ids: list[str] | list[UUID] | None,
    active_parameter_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default fields (no departments) cannot be deleted except by level 0
    - Fields linked to active parameters cannot be deleted
    - Must have field:delete permission
    """
    # Default fields can only be deleted by level 0
    if not field_department_ids and role_level > 0:
        return False

    # Fields with active parameter links cannot be deleted
    if active_parameter_count > 0:
        return False

    # Must have field:delete permission
    if not has_permission(role_permissions, "field", "delete"):
        return False

    # Department-subset guard: a non-top-level actor must belong to ALL
    # of the field's departments, else they could delete a field in a
    # department they cannot even view (mirrors ``eval.compute_can_delete``).
    if (
        user_department_ids is not None
        and role_level > 0
        and field_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        artifact_dept_set = {str(d) for d in field_department_ids}
        if not artifact_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_can_duplicate(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    field_department_ids: list[str] | list[UUID] | None = None,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Must have field:duplicate permission
    - Non-top-level users must belong to ALL of the field's departments
      (mirrors ``scenario.compute_can_duplicate`` — duplicate must not
      bypass the department scope ``has_access`` enforces, else a Dept-A
      user could clone a Dept-B field they cannot even view, inheriting
      its department scope into the copy).

    The department-subset check only runs when ``user_department_ids`` is
    supplied (the duplicate path passes it). List/get rendering callers that
    omit it keep the historical permission-only behaviour.
    """
    if not has_permission(role_permissions, "field", "duplicate"):
        return False

    if (
        user_department_ids is not None
        and role_level > 0
        and field_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        artifact_dept_set = {str(d) for d in field_department_ids}
        if not artifact_dept_set.issubset(user_dept_set):
            return False

    return True


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new field.

    Business logic:
    - Must have field:create permission
    - Non-level-0 users cannot create general objects (empty department_ids)
    """
    # Permission check first
    if not has_permission(role_permissions, "field", "create"):
        return False

    # Non-level-0 users cannot create general objects (no departments)
    if role_level > 0 and not department_ids:
        return False

    return True


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(
    role_level: int,
    role_permissions: list[tuple[str, str]],
) -> bool:
    """Compute permission to create or update a draft.

    Business logic:
    - Must have field:draft permission
    """
    return has_permission(role_permissions, "field", "draft")


# ========== Agent Scoring - Field-specific Constants ==========

# Field-specific resource definitions
FIELD_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
    "conditional_parameters",
}

# Multi-resource agent definitions for field
FIELD_BASIC_RESOURCES: set[str] = {"names", "descriptions", "flags", "departments"}
FIELD_GENERAL_RESOURCES: set[str] = FIELD_RESOURCES  # All resources
