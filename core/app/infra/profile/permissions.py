"""Profile permission helpers.

Extracts business logic from SQL into Python for the two-pass architecture.
These functions compute permissions, UI flags, and access control based on
data fetched from the Pass 1 SQL query.

Key difference from persona: Profile has actor/target distinction
(target_is_self flag, cannot delete own profile).

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
    "PROFILE_RESOURCES",
    "PROFILE_BASIC_RESOURCES",
    "PROFILE_GENERAL_RESOURCES",
]


def compute_can_edit(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    target_is_self: bool,
    target_department_ids: list[str] | list[UUID] | None,
    target_level: int | None = None,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Always allow editing self
    2. Level 0 (top-level) can edit all profiles
    3. If target_level provided, use level hierarchy (can only edit lower levels)
    4. Fallback: must have profile:update permission
    5. Non-level-0 users must belong to ALL of the target's departments
    """
    if target_is_self:
        return True

    if role_level == 0:
        return True

    # Must have profile:update permission to edit others
    if not has_permission(role_permissions, "profile", "update"):
        return False

    # List view: use level hierarchy (can only edit higher-numbered levels)
    if target_level is not None:
        if role_level >= target_level:
            return False

    # Department subset check (when user_department_ids is available)
    if user_department_ids is not None and target_department_ids:
        user_dept_set = {str(d) for d in user_department_ids}
        target_dept_set = {str(d) for d in target_department_ids}
        if not target_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_disabled_reason(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    target_is_self: bool,
    target_department_ids: list[str] | list[UUID] | None,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    if role_level == 0:
        return None

    if has_permission(role_permissions, "profile", "update"):
        return None

    if target_is_self:
        return None

    return (
        "This profile cannot be edited. "
        "You can view the details but cannot make changes."
    )


def has_access(
    role_level: int,
    user_department_ids: list[UUID] | None,
    target_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the profile.

    Access rules:
    - Level 0 (top-level) has access to all profiles
    - User has access if profile has no departments (default profile)
    - User has access if they share at least one department with the profile
    """
    if role_level == 0:
        return True

    # Default profiles (no departments) are accessible to all
    if not target_department_ids:
        return True

    # Check department overlap
    if not user_department_ids:
        return False

    user_dept_set = set(user_department_ids)
    target_dept_set = set(target_department_ids)
    return bool(user_dept_set & target_dept_set)


def compute_show_name(names_has_tools: bool) -> bool:
    """Determine if name picker should be shown."""
    return names_has_tools


def compute_show_emails(emails_has_tools: bool) -> bool:
    """Determine if emails picker should be shown."""
    return emails_has_tools


def compute_show_request_limit(request_limits_has_tools: bool) -> bool:
    """Determine if request_limit picker should be shown."""
    return request_limits_has_tools


def compute_show_flag() -> bool:
    """Determine if flag toggle should be shown."""
    return True


def compute_show_departments(departments_count: int) -> bool:
    """Determine if departments picker should be shown."""
    return departments_count > 0


def compute_name_required() -> bool:
    """Determine if name is required."""
    return True


def compute_emails_required() -> bool:
    """Determine if emails is required."""
    return False


def compute_request_limit_required() -> bool:
    """Determine if request_limit is required."""
    return False


def compute_flag_required() -> bool:
    """Determine if flag is required."""
    return False


def compute_departments_required() -> bool:
    """Determine if departments is required."""
    return False


def compute_show_roles() -> bool:
    """Determine if roles picker should be shown."""
    return True


def compute_roles_required() -> bool:
    """Determine if roles is required."""
    return False


def compute_role_options(role_level: int, all_roles: list[dict]) -> list[str]:
    """Compute which roles the user can assign, based on role level.

    Returns roles at or below the user's level (higher number = lower privilege).
    all_roles should be a list of dicts with 'name' and 'level' keys.
    """
    return [r["name"] for r in all_roles if r["level"] >= role_level]


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    target_is_self: bool,
    target_level: int | None = None,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Cannot delete own profile
    - Must have profile:delete permission
    - Can only delete users at a lower level (higher number)
    """
    if target_is_self:
        return False

    if not has_permission(role_permissions, "profile", "delete"):
        return False

    # Can only delete users at a strictly lower level
    if target_level is not None and role_level >= target_level:
        return False

    return True


def compute_can_duplicate(
    role_level: int,
    role_permissions: list[tuple[str, str]],
) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Must have profile:duplicate permission
    """
    return has_permission(role_permissions, "profile", "duplicate")


def compute_can_emulate(
    actor_role: str,
    target_role: str | None,
    target_is_self: bool,
) -> bool:
    """Compute can_emulate permission.

    Business logic:
    - Cannot emulate own profile
    - Target role must be in SIMULATABLE_ROLES for actor's role
    """
    from app.infra.identity.simulatable import SIMULATABLE_ROLES

    if target_is_self:
        return False

    if target_role is None:
        return False

    allowed_targets = SIMULATABLE_ROLES.get(actor_role, set())
    return target_role in allowed_targets


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new profile.

    Business logic:
    - Must have profile:create permission
    - Non-level-0 users cannot create general profiles (empty department_ids)
    """
    if not has_permission(role_permissions, "profile", "create"):
        return False

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
    - Must have profile:draft permission
    """
    return has_permission(role_permissions, "profile", "draft")


def get_missing_tools(
    names_has_tools: bool,
    emails_has_tools: bool,
    request_limits_has_tools: bool,
    show_departments: bool,
    departments_has_tools: bool,
) -> list[str]:
    """Get list of missing required tools."""
    missing = []

    if not names_has_tools:
        missing.append("name")
    if not emails_has_tools:
        missing.append("emails")
    if not request_limits_has_tools:
        missing.append("request_limits")
    if show_departments and not departments_has_tools:
        missing.append("departments")

    return missing


# ========== Agent Scoring - Profile-specific Constants ==========

# Profile-specific resource definitions
PROFILE_RESOURCES: set[str] = {
    "names",
    "emails",
    "request_limits",
    "flags",
    "departments",
    "roles",
}

# Multi-resource agent definitions for profile
PROFILE_BASIC_RESOURCES: set[str] = {"names", "emails", "flags", "request_limits"}
PROFILE_GENERAL_RESOURCES: set[str] = PROFILE_RESOURCES  # All resources

# ========== Domain Metadata - for client-side display in modals ==========

PROFILE_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "The display name for this profile",
        "icon": "user",
    },
    "emails": {
        "name": "Emails",
        "description": "Email addresses associated with this profile",
        "icon": "mail",
    },
    "request_limits": {
        "name": "Request Limit",
        "description": "Daily request limit for this profile",
        "icon": "gauge",
    },
    "flags": {
        "name": "Status",
        "description": "Active/inactive status",
        "icon": "flag",
    },
    "departments": {
        "name": "Departments",
        "description": "Which departments this profile belongs to",
        "icon": "building",
    },
}


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
) -> list:
    """Build rich domain metadata for client display.

    Delegates to shared build_domain_data with profile-specific metadata.
    """
    from app.infra.api_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, PROFILE_DOMAIN_METADATA
    )
