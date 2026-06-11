"""Provider permission helpers.

Extracts business logic from SQL into Python for the two-pass architecture.
These functions compute permissions, UI flags, and access control based on
data fetched from the Pass 1 SQL query.
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
    "PROVIDER_RESOURCES",
    "PROVIDER_BASIC_RESOURCES",
    "PROVIDER_GENERAL_RESOURCES",
]


def compute_can_edit(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    provider_department_ids: list[str] | list[UUID] | None,
    active_model_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Not a default provider (unless level 0)
    2. Not linked to active models
    3. User has provider update permission
    4. Non-level-0 users must belong to ALL of the provider's departments
    """
    # Default providers can only be edited by level 0
    if not provider_department_ids and role_level > 0:
        return False

    # Providers in use by active models cannot be edited
    if active_model_count > 0:
        return False

    # Permission check
    if not has_permission(role_permissions, "provider", "update"):
        return False

    # Department subset check (when user_department_ids is available)
    if (
        user_department_ids is not None
        and role_level > 0
        and provider_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        provider_dept_set = {str(d) for d in provider_department_ids}
        if not provider_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_disabled_reason(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    provider_department_ids: list[str] | list[UUID] | None,
    active_model_count: int,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    # Default providers can only be edited by level 0
    if not provider_department_ids and role_level > 0:
        return (
            "This is a default provider that cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Providers in use by active models cannot be edited
    if active_model_count > 0:
        return (
            "This provider is currently in use by models and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Permission check
    if not has_permission(role_permissions, "provider", "update"):
        return (
            "This provider cannot be edited. "
            "You can view the details but cannot make changes."
        )

    return None


def get_missing_tools(
    names_has_tools: bool,
    flags_has_tools: bool,
) -> list[str]:
    """Get list of missing required tools."""
    missing = []

    if not names_has_tools:
        missing.append("name")
    if not flags_has_tools:
        missing.append("flag")

    return missing


def has_access(
    role_level: int,
    user_department_ids: list[UUID] | None,
    provider_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the provider.

    Access rules:
    - Level 0 has access to all providers
    - User has access if provider has no departments (default provider)
    - User has access if they share at least one department with the provider
    """
    if role_level == 0:
        return True

    # Default providers (no departments) are accessible to all
    if not provider_department_ids:
        return True

    # Check department overlap
    if not user_department_ids:
        return False

    user_dept_set = set(user_department_ids)
    provider_dept_set = set(provider_department_ids)
    return bool(user_dept_set & provider_dept_set)


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


def compute_show_value() -> bool:
    """Determine if value picker should be shown."""
    return True


def compute_show_endpoint() -> bool:
    """Determine if endpoint picker should be shown."""
    return True


def compute_show_key() -> bool:
    """Determine if key picker should be shown."""
    return True


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


def compute_value_required() -> bool:
    """Determine if value is required."""
    return True


def compute_endpoint_required() -> bool:
    """Determine if endpoint is required."""
    return False


def compute_key_required() -> bool:
    """Determine if key is required."""
    return False


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    provider_department_ids: list[str] | list[UUID] | None,
    active_model_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default providers (no departments) cannot be deleted except by level 0
    - Providers linked to active models cannot be deleted
    - Only users with provider delete permission can delete
    """
    # Default providers can only be deleted by level 0
    if not provider_department_ids and role_level > 0:
        return False

    # Providers in use by active models cannot be deleted
    if active_model_count > 0:
        return False

    # Permission check
    if not has_permission(role_permissions, "provider", "delete"):
        return False

    # Department-subset guard: a non-top-level actor must belong to ALL
    # of the provider's departments, else they could delete a provider in a
    # department they cannot even view (mirrors ``eval.compute_can_delete``).
    if (
        user_department_ids is not None
        and role_level > 0
        and provider_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        artifact_dept_set = {str(d) for d in provider_department_ids}
        if not artifact_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_can_duplicate(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    provider_department_ids: list[str] | list[UUID] | None = None,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Must have provider:duplicate permission
    - Non-top-level users must belong to ALL of the provider's departments
      (mirrors ``scenario.compute_can_duplicate`` — duplicate must not
      bypass the department scope ``has_access`` enforces, else a Dept-A
      user could clone a Dept-B provider they cannot even view, inheriting
      its department scope into the copy).

    The department-subset check only runs when ``user_department_ids`` is
    supplied (the duplicate path passes it). List/get rendering callers that
    omit it keep the historical permission-only behaviour.
    """
    if not has_permission(role_permissions, "provider", "duplicate"):
        return False

    if (
        user_department_ids is not None
        and role_level > 0
        and provider_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        artifact_dept_set = {str(d) for d in provider_department_ids}
        if not artifact_dept_set.issubset(user_dept_set):
            return False

    return True


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new provider.

    Business logic:
    - Only users with provider create permission can create
    - Non-level-0 users cannot create general objects (empty department_ids)
    """
    # Permission check first
    if not has_permission(role_permissions, "provider", "create"):
        return False

    # Non-level-0 users cannot create general objects (no departments)
    if role_level > 0 and not department_ids:
        return False

    return True


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(role_level: int, role_permissions: list[tuple[str, str]]) -> bool:
    """Compute permission to create or update a draft.

    Business logic:
    - Only users with provider draft permission can create/edit drafts
    """
    return has_permission(role_permissions, "provider", "draft")


# ========== Agent Scoring - Provider-specific Constants ==========

# Provider-specific resource definitions
PROVIDER_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
    "values",
    "endpoints",
    "keys",
}

# Multi-resource agent definitions for provider
PROVIDER_BASIC_RESOURCES: set[str] = {"names", "descriptions", "flags", "departments"}
PROVIDER_GENERAL_RESOURCES: set[str] = PROVIDER_RESOURCES  # All resources
