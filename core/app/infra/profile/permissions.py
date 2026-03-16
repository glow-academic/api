"""Profile permission helpers.

Extracts business logic from SQL into Python for the two-pass architecture.
These functions compute permissions, UI flags, and access control based on
data fetched from the Pass 1 SQL query.

Key difference from persona: Profile has actor/target distinction
(target_is_self flag, cannot delete own profile).
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
    "PROFILE_RESOURCES",
    "PROFILE_BASIC_RESOURCES",
    "PROFILE_GENERAL_RESOURCES",
]

# Role hierarchy for list-view permission computation
ROLE_HIERARCHY = {
    "superadmin": 5,
    "admin": 4,
    "instructional": 3,
    "member": 2,
    "guest": 1,
    "custom": 1,
}


def compute_can_edit(
    user_role: str | None,
    target_is_self: bool,
    target_department_ids: list[str] | list[UUID] | None,
    target_role: str | None = None,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Always allow editing self
    2. Superadmin can edit all profiles
    3. If target_role provided, use role hierarchy (can only edit lower ranks)
    4. Fallback: admin can edit
    5. Non-superadmins must belong to ALL of the target's departments
    """
    if target_is_self:
        return True

    if user_role == "superadmin":
        return True

    # Only admin/instructional/superadmin can edit others
    if user_role not in ("admin", "instructional", "superadmin"):
        return False

    # List view: use role hierarchy (can only edit lower ranks)
    if target_role is not None:
        user_rank = ROLE_HIERARCHY.get(user_role or "", 0)
        target_rank = ROLE_HIERARCHY.get(target_role or "", 0)
        if user_rank <= target_rank:
            return False

    # Department subset check (when user_department_ids is available)
    if user_department_ids is not None and target_department_ids:
        user_dept_set = {str(d) for d in user_department_ids}
        target_dept_set = {str(d) for d in target_department_ids}
        if not target_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_disabled_reason(
    user_role: str | None,
    target_is_self: bool,
    target_department_ids: list[str] | list[UUID] | None,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    if user_role == "superadmin":
        return None

    if user_role in ("admin", "instructional"):
        return None

    if user_role == "staff" and target_is_self:
        return None

    if user_role == "staff":
        return (
            "You can only edit your own profile. "
            "Contact an administrator to make changes to other profiles."
        )

    if user_role == "learner":
        return (
            "You do not have permission to edit profiles. "
            "Contact an administrator to make changes."
        )

    return (
        "This profile cannot be edited. "
        "You can view the details but cannot make changes."
    )


def has_access(
    user_role: str | None,
    user_department_ids: list[UUID] | None,
    target_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the profile.

    Access rules:
    - Superadmin has access to all profiles
    - User has access if profile has no departments (default profile)
    - User has access if they share at least one department with the profile
    """
    if user_role == "superadmin":
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


def compute_role_options(user_role: str | None) -> list[str]:
    """Compute which roles the user can assign, based on role hierarchy.

    Superadmin can assign all roles, admin can assign admin and below,
    others can assign instructional and below.
    """
    all_roles = ["superadmin", "admin", "instructional", "member", "guest", "custom"]
    user_rank = ROLE_HIERARCHY.get(user_role or "", 0)

    return [r for r in all_roles if ROLE_HIERARCHY.get(r, 0) <= user_rank]


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    user_role: str | None,
    target_is_self: bool,
    target_role: str | None = None,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Cannot delete own profile
    - Only admin/superadmin can delete (can only delete lower ranks)
    """
    if target_is_self:
        return False

    # Only admin/superadmin can delete
    if user_role not in ("admin", "superadmin"):
        return False

    # Superadmin can delete anyone (except self, checked above)
    if user_role == "superadmin":
        return True

    # Use role hierarchy: can only delete lower ranks
    if target_role is not None:
        user_rank = ROLE_HIERARCHY.get(user_role or "", 0)
        target_rank = ROLE_HIERARCHY.get(target_role or "", 0)
        return user_rank > target_rank

    # Fallback: admin can delete
    return user_role == "admin"


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
    """Compute permission to create a new profile.

    Business logic:
    - Non-superadmins cannot create general objects (empty department_ids)
    - Only admin/superadmin can create profiles
    """
    _ = department_ids
    return user_role in ("admin", "superadmin")


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(user_role: str | None) -> bool:
    """Compute permission to create or update a draft.

    Business logic:
    - Only admin/superadmin can create/edit drafts
    """
    return user_role in ("admin", "superadmin")


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
    from app.infra.v5_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, PROFILE_DOMAIN_METADATA
    )
