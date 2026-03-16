"""Auth permission helpers.

Extracts business logic from SQL into Python for the two-pass architecture.
These functions compute permissions, UI flags, and access control based on
data fetched from the Pass 1 SQL query.

Auth permissions are simpler than persona: no department-based access,
no scenario constraints. Just role-based (admin/superadmin).
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
    "AUTH_RESOURCES",
    "AUTH_BASIC_RESOURCES",
]


def compute_can_edit(
    user_role: str | None,
    active_settings_count: int = 0,
) -> bool:
    """Unified can_edit logic for both get and list views.

    Constraints:
    1. Not linked to active settings
    2. User has superadmin role
    """
    if active_settings_count > 0:
        return False

    return user_role == "superadmin"


def compute_disabled_reason(
    user_role: str | None,
    active_settings_count: int = 0,
) -> str | None:
    """Compute the reason why editing is disabled, if any."""
    if active_settings_count > 0:
        return (
            "This auth entry is currently linked to settings and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    if user_role != "superadmin":
        return (
            "This auth entry cannot be edited. "
            "You can view the details but cannot make changes."
        )
    return None


def compute_can_delete(
    user_role: str | None,
    active_settings_count: int = 0,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Auths linked to active settings cannot be deleted
    - Only superadmins can delete
    """
    if active_settings_count > 0:
        return False

    return user_role == "superadmin"


def compute_can_duplicate(user_role: str | None) -> bool:
    """Compute can_duplicate permission."""
    return user_role == "superadmin"


def compute_can_create(user_role: str | None) -> bool:
    """Compute permission to create a new auth."""
    return user_role == "superadmin"


def compute_can_draft(user_role: str | None) -> bool:
    """Compute permission to create or update a draft."""
    return user_role == "superadmin"


def has_access(user_role: str | None) -> bool:
    """Auth view access follows the current route contract: any signed-in profile."""
    return user_role is not None


def compute_show_name(names_has_tools: bool) -> bool:
    """Determine if name picker should be shown."""
    return names_has_tools


def compute_show_description() -> bool:
    """Always show description picker."""
    return True


def compute_show_flag() -> bool:
    """Flag is a boolean toggle that should always be shown."""
    return True


def compute_show_protocols(protocols_has_tools: bool, protocols_count: int) -> bool:
    """Determine if protocols picker should be shown."""
    return protocols_has_tools and protocols_count > 0


def compute_show_slugs(slugs_has_tools: bool, slugs_count: int) -> bool:
    """Determine if slugs picker should be shown."""
    return slugs_has_tools and slugs_count > 0


def compute_name_required() -> bool:
    return True


def compute_description_required() -> bool:
    return False


def compute_flag_required() -> bool:
    return False


def compute_protocols_required(show_protocols: bool) -> bool:
    return show_protocols


def compute_slugs_required(show_slugs: bool) -> bool:
    return show_slugs


# ========== Agent Scoring - Auth-specific Constants ==========

AUTH_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "protocols",
    "slugs",
    "items",
}

# Multi-resource agent definitions for auth
AUTH_BASIC_RESOURCES: set[str] = {"names", "descriptions", "flags"}
AUTH_GENERAL_RESOURCES: set[str] = AUTH_RESOURCES

# ========== Domain Metadata ==========

AUTH_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "The display name for this auth entry",
        "icon": "key",
    },
    "descriptions": {
        "name": "Description",
        "description": "A brief description of this auth entry",
        "icon": "file-text",
    },
    "flags": {
        "name": "Status",
        "description": "Active/inactive status",
        "icon": "flag",
    },
    "protocols": {
        "name": "Protocols",
        "description": "Authentication protocols (e.g., OAuth, SAML)",
        "icon": "shield",
    },
    "slugs": {
        "name": "Slugs",
        "description": "URL slugs for this auth entry",
        "icon": "link",
    },
}


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
) -> list:
    """Build rich domain metadata for client display."""
    from app.infra.v5_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, AUTH_DOMAIN_METADATA
    )
