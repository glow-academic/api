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
from app.infra.v5_types import CandidateAgent

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
    user_role: str | None,
    provider_department_ids: list[str] | list[UUID] | None,
    active_model_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Not a default provider (unless superadmin)
    2. Not linked to active models
    3. User has admin/superadmin role
    4. Non-superadmins must belong to ALL of the provider's departments
    """
    # Default providers can only be edited by superadmin
    if not provider_department_ids and user_role != "superadmin":
        return False

    # Providers in use by active models cannot be edited
    if active_model_count > 0:
        return False

    # Role check
    if user_role not in ("admin", "superadmin"):
        return False

    # Department subset check (when user_department_ids is available)
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and provider_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        provider_dept_set = {str(d) for d in provider_department_ids}
        if not provider_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_disabled_reason(
    user_role: str | None,
    provider_department_ids: list[str] | list[UUID] | None,
    active_model_count: int,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    # Default providers can only be edited by superadmin
    if not provider_department_ids and user_role != "superadmin":
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

    # Role check
    if user_role not in ("admin", "superadmin"):
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
    user_role: str | None,
    user_department_ids: list[UUID] | None,
    provider_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the provider.

    Access rules:
    - Superadmin has access to all providers
    - User has access if provider has no departments (default provider)
    - User has access if they share at least one department with the provider
    """
    if user_role == "superadmin":
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
    user_role: str | None,
    provider_department_ids: list[str] | list[UUID] | None,
    active_model_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default providers (no departments) cannot be deleted except by superadmin
    - Providers linked to active models cannot be deleted
    - Only admins and superadmins can delete
    """
    # Default providers can only be deleted by superadmin
    if not provider_department_ids and user_role != "superadmin":
        return False

    # Providers in use by active models cannot be deleted
    if active_model_count > 0:
        return False

    # Only admins and superadmins can delete
    return user_role in ("admin", "superadmin")


def compute_can_duplicate(user_role: str | None) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Only admin/superadmin can duplicate
    """
    return user_role in ("admin", "superadmin")


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    user_role: str | None,
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new provider.

    Business logic:
    - Non-superadmins cannot create general objects (empty department_ids)
    - Only admin/superadmin can create providers
    """
    # Role check first
    if user_role not in ("admin", "superadmin"):
        return False

    # Non-superadmins cannot create general objects (no departments)
    if user_role != "superadmin" and not department_ids:
        return False

    return True


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(user_role: str | None) -> bool:
    """Compute permission to create or update a draft.

    Business logic:
    - Only admin/superadmin can create/edit drafts
    """
    return user_role in ("admin", "superadmin")


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
