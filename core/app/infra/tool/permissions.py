"""Tool permission helpers.

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
    "TOOL_RESOURCES",
    "compute_show_permissions",
    "compute_permissions_required",
]


def compute_can_edit(
    role_level: int, role_permissions: list[tuple[str, str]],
    active_agent_count: int,
) -> bool:
    """Unified can_edit logic for both get and list views.

    Constraints:
    1. Not linked to active agents
    2. User has tool update permission
    """
    # Tools in use by active agents cannot be edited
    if active_agent_count > 0:
        return False

    # Permission check
    return has_permission(role_permissions, "tool", "update")


def compute_disabled_reason(
    role_permissions: list[tuple[str, str]],
    active_agent_count: int,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    # Tools in use by active agents cannot be edited
    if active_agent_count > 0:
        return (
            "This tool is currently in use by agents and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Permission check
    if not has_permission(role_permissions, "tool", "update"):
        return (
            "This tool cannot be edited. "
            "You can view the details but cannot make changes."
        )

    return None


def get_missing_tools(
    names_has_tools: bool,
    show_args: bool,
    args_has_tools: bool,
    show_arg_positions: bool,
    arg_positions_has_tools: bool,
    show_args_outputs: bool,
    args_outputs_has_tools: bool,
) -> list[str]:
    """Get list of missing required tools."""
    missing = []

    if not names_has_tools:
        missing.append("name")
    if show_args and not args_has_tools:
        missing.append("args")
    if show_arg_positions and not arg_positions_has_tools:
        missing.append("arg_positions")
    if show_args_outputs and not args_outputs_has_tools:
        missing.append("args_outputs")

    return missing


def has_access(
    role_level: int,
) -> bool:
    """Check if user has access to view the tool.

    Access rules:
    - Tools are accessible to all authenticated users (no department scoping)
    """
    return role_level is not None


def compute_show_name(names_has_tools: bool) -> bool:
    """Determine if name picker should be shown."""
    return names_has_tools


def compute_show_description() -> bool:
    """Determine if description picker should be shown."""
    return True


def compute_show_args(args_count: int) -> bool:
    """Determine if args picker should be shown."""
    return args_count > 0


def compute_show_args_outputs(args_outputs_count: int) -> bool:
    """Determine if args_outputs picker should be shown."""
    return args_outputs_count > 0


def compute_show_arg_positions(arg_positions_count: int, args_count: int) -> bool:
    """Determine if arg_positions picker should be shown."""
    return arg_positions_count > 0 or args_count > 0


def compute_show_flag() -> bool:
    """Determine if flag toggle should be shown."""
    return True


def compute_name_required() -> bool:
    """Determine if name is required."""
    return True


def compute_description_required() -> bool:
    """Determine if description is required."""
    return False


def compute_args_required() -> bool:
    """Determine if args is required."""
    return False


def compute_args_outputs_required() -> bool:
    """Determine if args_outputs is required."""
    return False


def compute_flag_required() -> bool:
    """Determine if flag is required."""
    return False


def compute_show_permissions(total_permissions: int = 0) -> bool:
    """Determine if permissions picker should be shown."""
    return True


def compute_permissions_required() -> bool:
    """Determine if permissions is required."""
    return False


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    role_level: int, role_permissions: list[tuple[str, str]],
    active_agent_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Tools linked to active agents cannot be deleted
    - Only users with tool delete permission can delete
    """
    if active_agent_count > 0:
        return False

    return has_permission(role_permissions, "tool", "delete")


def compute_can_duplicate(role_level: int, role_permissions: list[tuple[str, str]]) -> bool:
    """Compute can_duplicate permission."""
    return has_permission(role_permissions, "tool", "duplicate")


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    role_level: int, role_permissions: list[tuple[str, str]],
) -> bool:
    """Compute permission to create a new tool."""
    return has_permission(role_permissions, "tool", "create")


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(role_level: int, role_permissions: list[tuple[str, str]]) -> bool:
    """Compute permission to create or update a draft."""
    return has_permission(role_permissions, "tool", "draft")


# ========== Agent Scoring - Tool-specific Constants ==========

# Tool-specific resource definitions
TOOL_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "args",
    "arg_positions",
    "args_outputs",
    "flags",
    "permissions",
}

# ========== Domain Metadata - for client-side display in modals ==========

TOOL_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "The display name for this tool",
        "icon": "wrench",
    },
    "descriptions": {
        "name": "Description",
        "description": "A brief description of what this tool does",
        "icon": "file-text",
    },
    "args": {
        "name": "Arguments",
        "description": "Input arguments for this tool",
        "icon": "list",
    },
    "args_outputs": {
        "name": "Output Templates",
        "description": "Output templates for each argument",
        "icon": "file-output",
    },
    "arg_positions": {
        "name": "Argument Positions",
        "description": "Ordering of tool arguments",
        "icon": "arrow-up-down",
    },
    "flags": {
        "name": "Status",
        "description": "Active/inactive status",
        "icon": "flag",
    },
}


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
) -> list:
    """Build rich domain metadata for client display.

    Delegates to shared build_domain_data with tool-specific metadata.
    """
    from app.infra.api_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, TOOL_DOMAIN_METADATA
    )
