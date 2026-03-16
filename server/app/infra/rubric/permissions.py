"""Rubric permission helpers.

Extracts business logic from SQL into Python for the two-pass architecture.
These functions compute permissions, UI flags, and access control based on
data fetched from the Pass 1 SQL query.
"""

from uuid import UUID

__all__ = [
    "RUBRIC_RESOURCES",
    "RUBRIC_BASIC_RESOURCES",
    "RUBRIC_CONTENT_RESOURCES",
]


def compute_can_edit(
    user_role: str | None,
    rubric_department_ids: list[str] | list[UUID] | None,
    active_simulation_count: int,
) -> bool:
    """Unified can_edit logic for both get and list views.

    Constraints:
    1. Not a default rubric (unless superadmin)
    2. Not linked to active simulations
    3. User has superadmin role
    """
    if not rubric_department_ids and user_role != "superadmin":
        return False

    if active_simulation_count > 0:
        return False

    return user_role == "superadmin"


def compute_disabled_reason(
    user_role: str | None,
    rubric_department_ids: list[str] | list[UUID] | None,
    active_simulation_count: int,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    if not rubric_department_ids and user_role != "superadmin":
        return (
            "This is a default rubric that cannot be edited. "
            "You can view the details but cannot make changes."
        )

    if active_simulation_count > 0:
        return (
            "This rubric is currently in use by simulations and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    if user_role != "superadmin":
        return (
            "This rubric cannot be edited. "
            "You can view the details but cannot make changes."
        )

    return None


def has_access(
    user_role: str | None,
    user_department_ids: list[UUID] | None,
    rubric_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the rubric.

    Access rules:
    - Superadmin has access to all rubrics
    - User has access if rubric has no departments (default rubric)
    - User has access if they share at least one department with the rubric
    """
    if user_role == "superadmin":
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
    user_role: str | None,
    rubric_department_ids: list[str] | None,
    active_simulation_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default rubrics (no departments) cannot be deleted except by superadmin
    - Rubrics linked to active simulations cannot be deleted
    - Only superadmins can delete
    """
    if not rubric_department_ids and user_role != "superadmin":
        return False

    if active_simulation_count > 0:
        return False

    return user_role == "superadmin"


def compute_can_duplicate(user_role: str | None) -> bool:
    """Compute can_duplicate permission."""
    return user_role == "superadmin"


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    user_role: str | None,
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new rubric."""
    if user_role != "superadmin":
        return False

    return True


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(user_role: str | None) -> bool:
    """Compute permission to create or update a draft."""
    return user_role == "superadmin"


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
    from app.infra.v5_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, RUBRIC_DOMAIN_METADATA
    )
