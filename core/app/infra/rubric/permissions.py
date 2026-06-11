"""Rubric permission helpers.

Extracts business logic from SQL into Python for the two-pass architecture.
These functions compute permissions, UI flags, and access control based on
data fetched from the Pass 1 SQL query.

Fully generic — no knowledge of specific role names.
All checks use two mechanisms:
  1. Permission set: (artifact, operation) tuples from role's permission_ids
  2. Role level: integer hierarchy (0 = highest privilege)
"""

from uuid import UUID

from app.infra.permissions_helpers import has_permission

__all__ = [
    "RUBRIC_RESOURCES",
    "RUBRIC_BASIC_RESOURCES",
    "RUBRIC_CONTENT_RESOURCES",
]


def compute_can_edit(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    rubric_department_ids: list[str] | list[UUID] | None,
    active_simulation_count: int,
) -> bool:
    """Unified can_edit logic for both get and list views.

    Constraints:
    1. Not a default rubric (unless level 0)
    2. Not linked to active simulations
    3. User has rubric:update permission
    """
    if not rubric_department_ids and role_level > 0:
        return False

    if active_simulation_count > 0:
        return False

    return has_permission(role_permissions, "rubric", "update")


def compute_disabled_reason(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    rubric_department_ids: list[str] | list[UUID] | None,
    active_simulation_count: int,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    if not rubric_department_ids and role_level > 0:
        return (
            "This is a default rubric that cannot be edited. "
            "You can view the details but cannot make changes."
        )

    if active_simulation_count > 0:
        return (
            "This rubric is currently in use by simulations and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    if not has_permission(role_permissions, "rubric", "update"):
        return (
            "This rubric cannot be edited. "
            "You can view the details but cannot make changes."
        )

    return None


def has_access(
    role_level: int,
    user_department_ids: list[UUID] | None,
    rubric_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the rubric.

    Access rules:
    - Level 0 (top-level) has access to all rubrics
    - User has access if rubric has no departments (default rubric)
    - User has access if they share at least one department with the rubric
    """
    if role_level == 0:
        return True

    if not rubric_department_ids:
        return True

    if not user_department_ids:
        return False

    user_dept_set = set(user_department_ids)
    rubric_dept_set = set(rubric_department_ids)
    return bool(user_dept_set & rubric_dept_set)


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


def compute_show_points() -> bool:
    """Determine if points picker should be shown."""
    return True


def compute_show_standard_groups() -> bool:
    """Determine if standard groups picker should be shown."""
    return True


def compute_show_standards(standard_group_count: int) -> bool:
    """Determine if standards picker should be shown."""
    return standard_group_count > 0


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


def compute_points_required() -> bool:
    """Determine if total points is required."""
    return True


def compute_standard_groups_required() -> bool:
    """Determine if standard groups is required."""
    return True


def compute_standards_required() -> bool:
    """Determine if standards is required."""
    return True


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    rubric_department_ids: list[str] | None,
    active_simulation_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default rubrics (no departments) cannot be deleted except by level 0
    - Rubrics linked to active simulations cannot be deleted
    - Must have rubric:delete permission
    """
    if not rubric_department_ids and role_level > 0:
        return False

    if active_simulation_count > 0:
        return False

    if not has_permission(role_permissions, "rubric", "delete"):
        return False

    # Department-subset guard: a non-top-level actor must belong to ALL
    # of the rubric's departments, else they could delete a rubric in a
    # department they cannot even view (mirrors ``eval.compute_can_delete``).
    if (
        user_department_ids is not None
        and role_level > 0
        and rubric_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        artifact_dept_set = {str(d) for d in rubric_department_ids}
        if not artifact_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_can_duplicate(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    rubric_department_ids: list[str] | list[UUID] | None = None,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Must have rubric:duplicate permission
    - Non-top-level users must belong to ALL of the rubric's departments
      (mirrors ``scenario.compute_can_duplicate`` — duplicate must not
      bypass the department scope ``has_access`` enforces, else a Dept-A
      user could clone a Dept-B rubric they cannot even view, inheriting
      its department scope into the copy).

    The department-subset check only runs when ``user_department_ids`` is
    supplied (the duplicate path passes it). List/get rendering callers that
    omit it keep the historical permission-only behaviour.
    """
    if not has_permission(role_permissions, "rubric", "duplicate"):
        return False

    if (
        user_department_ids is not None
        and role_level > 0
        and rubric_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        artifact_dept_set = {str(d) for d in rubric_department_ids}
        if not artifact_dept_set.issubset(user_dept_set):
            return False

    return True


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new rubric.

    Business logic:
    - Must have rubric:create permission
    - Non-level-0 users cannot create general rubrics (empty department_ids)
    """
    if not has_permission(role_permissions, "rubric", "create"):
        return False

    if role_level > 0 and not department_ids:
        return False

    return True


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(
    role_level: int,
    role_permissions: list[tuple[str, str]],
) -> bool:
    """Compute permission to create or update a draft."""
    return has_permission(role_permissions, "rubric", "draft")


# ========== Agent Scoring - Rubric-specific Constants ==========

RUBRIC_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "departments",
    "flags",
    "points",
    "standard_groups",
    "standards",
}

RUBRIC_BASIC_RESOURCES: set[str] = {"names", "descriptions", "flags", "departments"}
RUBRIC_CONTENT_RESOURCES: set[str] = {
    "points",
    "standard_groups",
    "standards",
}

# ========== Domain Metadata - for client-side display in modals ==========

RUBRIC_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "The display name for this rubric",
        "icon": "file-text",
    },
    "descriptions": {
        "name": "Description",
        "description": "A brief description of this rubric",
        "icon": "file-text",
    },
    "departments": {
        "name": "Departments",
        "description": "Which departments can access this rubric",
        "icon": "building",
    },
    "flags": {
        "name": "Status",
        "description": "Active/inactive status",
        "icon": "flag",
    },
    "points": {
        "name": "Total Points",
        "description": "The total points available in this rubric",
        "icon": "hash",
    },
    "standard_groups": {
        "name": "Standard Groups",
        "description": "Groups of standards for organizing the rubric",
        "icon": "layers",
    },
    "standards": {
        "name": "Standards",
        "description": "Individual standards within the rubric",
        "icon": "list",
    },
}


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
) -> list:
    """Build rich domain metadata for client display.

    Delegates to shared build_domain_data with rubric-specific metadata.
    """
    from app.infra.api_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, RUBRIC_DOMAIN_METADATA
    )
