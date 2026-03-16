"""Agent permission helpers.

Extracts business logic from SQL into Python for the two-pass architecture.
These functions compute permissions, UI flags, and access control based on
data fetched from the Pass 1 SQL query.

Key difference from profile: Agent has 11 resources (vs profile's 6),
includes content-oriented resources (prompts, instructions), and uses
department-based access control without actor/target distinction.
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
    "AGENT_RESOURCES",
    "AGENT_BASIC_RESOURCES",
    "AGENT_CONTENT_RESOURCES",
    "AGENT_GENERAL_RESOURCES",
]

# ========== Access Control ==========


def has_access(
    user_role: str | None,
    user_department_ids: list[UUID] | None,
    agent_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to this agent.

    Access rules:
    - Superadmin has access to all agents
    - If agent has no departments, everyone has access
    - User must share at least one department with the agent
    """
    if user_role == "superadmin":
        return True

    # Agents with no departments are accessible to all
    if not agent_department_ids:
        return True

    # Check department overlap
    if not user_department_ids:
        return False

    return bool(set(user_department_ids) & set(agent_department_ids))


def compute_can_edit(
    user_role: str | None,
    has_agent_access: bool,
    missing_tools: list[str],
    agent_id: UUID | None = None,
) -> bool:
    """Compute whether user can edit this agent.

    Constraints:
    1. New mode (agent_id is None): can edit if no critical tools missing
    2. Detail mode: must have access and no missing tools
    """
    if agent_id is None:
        return len(missing_tools) == 0

    return has_agent_access and len(missing_tools) == 0


def compute_disabled_reason(
    user_role: str | None,
    has_agent_access: bool,
    missing_tools: list[str],
    agent_id: UUID | None = None,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    if agent_id is not None and not has_agent_access:
        return (
            "You don't have access to this agent. "
            "It may be restricted to other departments."
        )

    if missing_tools:
        return (
            f"No tool configured for {', '.join(missing_tools)}. "
            "Therefore we cannot proceed ahead."
        )

    return None


# ========== Show Flags ==========


def compute_show_name(names_has_tools: bool) -> bool:
    """Determine if name picker should be shown."""
    return names_has_tools


def compute_show_description(descriptions_has_tools: bool) -> bool:
    """Determine if description picker should be shown."""
    return descriptions_has_tools


def compute_show_models(models_has_tools: bool) -> bool:
    """Determine if model picker should be shown."""
    return models_has_tools


def compute_show_prompts(prompts_has_tools: bool) -> bool:
    """Determine if prompt picker should be shown."""
    return prompts_has_tools


def compute_show_instructions(instructions_has_tools: bool) -> bool:
    """Determine if instructions picker should be shown."""
    return instructions_has_tools


def compute_show_flag() -> bool:
    """Determine if flag toggle should be shown."""
    return True


def compute_show_departments(
    departments_has_tools: bool, has_departments: bool
) -> bool:
    """Determine if departments picker should be shown."""
    if not departments_has_tools and has_departments:
        return False
    return has_departments


def compute_show_tools(tools_has_tools: bool, has_any_tools: bool) -> bool:
    """Determine if tools picker should be shown."""
    if not tools_has_tools:
        return False
    return has_any_tools


def compute_show_reasoning_levels(reasoning_levels_has_tools: bool) -> bool:
    """Determine if reasoning level picker should be shown."""
    return reasoning_levels_has_tools


def compute_show_temperature_levels(temperature_levels_has_tools: bool) -> bool:
    """Determine if temperature level picker should be shown."""
    return temperature_levels_has_tools


def compute_show_voices(voices_has_tools: bool) -> bool:
    """Determine if voice picker should be shown."""
    return voices_has_tools


# ========== Required Flags ==========


def compute_name_required() -> bool:
    """Determine if name is required."""
    return True


def compute_description_required() -> bool:
    """Determine if description is required."""
    return False


def compute_models_required() -> bool:
    """Determine if model is required."""
    return True


def compute_prompts_required() -> bool:
    """Determine if prompt is required."""
    return False


def compute_instructions_required() -> bool:
    """Determine if instructions is required."""
    return False


def compute_flag_required() -> bool:
    """Determine if flag is required."""
    return False


def compute_departments_required(show_departments: bool) -> bool:
    """Determine if departments is required."""
    return show_departments


def compute_tools_required() -> bool:
    """Determine if tools is required."""
    return False


def compute_reasoning_levels_required() -> bool:
    """Determine if reasoning level is required."""
    return False


def compute_temperature_levels_required() -> bool:
    """Determine if temperature level is required."""
    return False


def compute_voices_required() -> bool:
    """Determine if voice is required."""
    return False


def compute_show_qualities(qualities_has_tools: bool) -> bool:
    """Determine if quality picker should be shown."""
    return qualities_has_tools


def compute_qualities_required() -> bool:
    """Determine if quality is required."""
    return False


def compute_show_rubrics(rubrics_has_tools: bool) -> bool:
    """Determine if rubrics picker should be shown."""
    return rubrics_has_tools


def compute_rubrics_required() -> bool:
    """Determine if rubrics is required."""
    return False


# ========== List Endpoint Permission Functions ==========


def compute_list_can_edit(
    user_role: str | None,
    agent_department_ids: list[str] | None,
    active_settings_count: int = 0,
) -> bool:
    """Compute can_edit for list view.

    Business logic:
    - Default agents (no departments) can only be edited by superadmin
    - Agents linked to active settings cannot be edited
    - Only admins and superadmins can edit agents
    """
    if not agent_department_ids and user_role != "superadmin":
        return False
    if active_settings_count > 0:
        return False
    return user_role in ("admin", "superadmin")


def compute_can_delete(
    user_role: str | None,
    active_settings_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Agents linked to active settings cannot be deleted
    - Only admins and superadmins can delete
    """
    if user_role not in ("superadmin", "admin"):
        return False

    return active_settings_count == 0


def compute_can_duplicate(user_role: str | None) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Agent can be duplicated by admins and above
    """
    return user_role in ("superadmin", "admin")


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    user_role: str | None,
    user_department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new agent.

    Business logic:
    - Only admin/superadmin can create agents
    - Non-superadmins cannot create general objects (no departments)
    """
    if user_role not in ("admin", "superadmin"):
        return False

    if user_role != "superadmin" and not user_department_ids:
        return False

    return True


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(user_role: str | None) -> bool:
    """Compute permission to create or update a draft.

    Business logic:
    - Only admin/superadmin can create/edit drafts
    """
    return user_role in ("superadmin", "admin")


# ========== Helpers ==========


def get_missing_tools(
    names_has_tools: bool,
    models_has_tools: bool,
    prompts_has_tools: bool,
    instructions_has_tools: bool,
) -> list[str]:
    """Get list of missing critical tools (name, model are always required)."""
    missing: list[str] = []

    if not names_has_tools:
        missing.append("name")
    if not models_has_tools:
        missing.append("model")
    if not prompts_has_tools:
        missing.append("prompt")
    if not instructions_has_tools:
        missing.append("instructions")

    return missing


# ========== Agent Scoring - Agent-specific Constants ==========

# Agent-specific resource definitions
AGENT_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "models",
    "prompts",
    "instructions",
    "flags",
    "departments",
    "tools",
    "temperature_levels",
    "reasoning_levels",
    "voices",
    "qualities",
    "rubrics",
}

# Resources that require an active tool to show AI generate button
AGENT_BASIC_RESOURCES: set[str] = {"names", "descriptions", "models", "flags"}

# Resources that are content-oriented (prompts, instructions)
AGENT_CONTENT_RESOURCES: set[str] = {"prompts", "instructions"}

# All resources that support AI generation
AGENT_GENERAL_RESOURCES: set[str] = AGENT_RESOURCES

# ========== Domain Metadata - for client-side display in modals ==========

AGENT_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "Agent name",
        "icon": "bot",
    },
    "descriptions": {
        "name": "Description",
        "description": "Agent description",
        "icon": "text",
    },
    "models": {
        "name": "Model",
        "description": "AI model",
        "icon": "cpu",
    },
    "prompts": {
        "name": "Prompt",
        "description": "System prompt",
        "icon": "message-square",
    },
    "instructions": {
        "name": "Instructions",
        "description": "Agent instructions",
        "icon": "file-text",
    },
    "flags": {
        "name": "Active",
        "description": "Active status",
        "icon": "flag",
    },
    "departments": {
        "name": "Departments",
        "description": "Department assignments",
        "icon": "building",
    },
    "tools": {
        "name": "Tools",
        "description": "Available tools",
        "icon": "wrench",
    },
    "temperature_levels": {
        "name": "Temperature",
        "description": "Temperature level",
        "icon": "thermometer",
    },
    "reasoning_levels": {
        "name": "Reasoning",
        "description": "Reasoning level",
        "icon": "brain",
    },
    "voices": {
        "name": "Voice",
        "description": "Voice selection",
        "icon": "mic",
    },
    "qualities": {
        "name": "Quality",
        "description": "Quality settings",
        "icon": "sparkles",
    },
    "rubrics": {
        "name": "Rubrics",
        "description": "Evaluation rubrics",
        "icon": "clipboard-check",
    },
}


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
) -> list:
    """Build rich domain metadata for client display.

    Delegates to shared build_domain_data with agent-specific metadata.
    """
    from app.infra.v5_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, AGENT_DOMAIN_METADATA
    )
