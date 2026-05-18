"""Model permission helpers.

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
    "MODEL_RESOURCES",
    "MODEL_BASIC_RESOURCES",
    "MODEL_PROVIDER_RESOURCES",
    "MODEL_FEATURES_RESOURCES",
]


def compute_can_edit(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    model_department_ids: list[str] | list[UUID] | None,
    active_agent_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Default models (no departments) can only be edited by level 0
    2. Models linked to active agents cannot be edited
    3. User has model update permission
    4. Non-level-0 users must belong to ALL of the model's departments
    """
    if not model_department_ids and role_level > 0:
        return False
    if active_agent_count > 0:
        return False
    if not has_permission(role_permissions, "model", "update"):
        return False
    # Department subset check (when user_department_ids is available)
    if (
        user_department_ids is not None
        and role_level > 0
        and model_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        model_dept_set = {str(d) for d in model_department_ids}
        if not model_dept_set.issubset(user_dept_set):
            return False
    return True


def compute_disabled_reason(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    model_department_ids: list[str] | list[UUID] | None,
    active_agent_count: int,
) -> str | None:
    """Compute the reason why editing is disabled, if any."""
    if not model_department_ids and role_level > 0:
        return (
            "This is a default model that cannot be edited. "
            "You can view the details but cannot make changes."
        )
    if active_agent_count > 0:
        return (
            "This model is currently in use by agents and cannot be edited. "
            "You can view the details but cannot make changes."
        )
    if not has_permission(role_permissions, "model", "update"):
        return (
            "This model cannot be edited. "
            "You can view the details but cannot make changes."
        )
    return None


def has_access(
    role_level: int,
    user_department_ids: list[UUID] | None,
    model_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the model."""
    if role_level == 0:
        return True
    if not model_department_ids:
        return True
    if not user_department_ids:
        return False
    user_dept_set = set(user_department_ids)
    model_dept_set = set(model_department_ids)
    return bool(user_dept_set & model_dept_set)


# ========== Show/Required Functions ==========


def compute_show_name(names_has_tools: bool) -> bool:
    return names_has_tools


def compute_show_description() -> bool:
    return True


def compute_show_flag() -> bool:
    return True


def compute_show_value(values_has_tools: bool) -> bool:
    return values_has_tools


def compute_show_provider() -> bool:
    return True


def compute_show_departments(departments_count: int) -> bool:
    return departments_count > 0


def compute_show_modalities() -> bool:
    return True


def compute_show_temperature_levels() -> bool:
    return True


def compute_show_reasoning_levels() -> bool:
    return True


def compute_show_qualities() -> bool:
    return True


def compute_show_voices() -> bool:
    return True


def compute_name_required() -> bool:
    return True


def compute_description_required() -> bool:
    return False


def compute_flag_required() -> bool:
    return False


def compute_value_required() -> bool:
    return True


def compute_provider_required() -> bool:
    return True


def compute_departments_required() -> bool:
    return False


def compute_modalities_required() -> bool:
    return False


def compute_temperature_levels_required() -> bool:
    return False


def compute_reasoning_levels_required() -> bool:
    return False


def compute_qualities_required() -> bool:
    return False


def compute_pricing_required() -> bool:
    return False


def compute_voices_required() -> bool:
    return False


def compute_show_pricing() -> bool:
    return True


# ========== Show AI Generate ==========


def compute_show_ai_generate(agent_ids: dict[str, UUID | None], resource: str) -> bool:
    """Returns True if an agent is configured for the resource."""
    return agent_ids.get(resource) is not None


# ========== Derive Flag Key/Label ==========


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name.
    Example: 'model_active' -> ('active', 'Active')
    """
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("model_", "")
    label = key.replace("_", " ").title()
    return (key, label)


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    model_department_ids: list[str] | None,
    active_agent_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default models (no departments) cannot be deleted except by level 0
    - Models linked to active agents cannot be deleted
    - Only users with model delete permission can delete
    """
    if not model_department_ids and role_level > 0:
        return False
    if active_agent_count > 0:
        return False
    return has_permission(role_permissions, "model", "delete")


def compute_can_duplicate(role_level: int, role_permissions: list[tuple[str, str]]) -> bool:
    return has_permission(role_permissions, "model", "duplicate")


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    role_level: int,
    role_permissions: list[tuple[str, str]],
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    if not has_permission(role_permissions, "model", "create"):
        return False
    if role_level > 0 and not department_ids:
        return False
    return True


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(role_level: int, role_permissions: list[tuple[str, str]]) -> bool:
    return has_permission(role_permissions, "model", "draft")


# ========== Model-specific Resource Definitions ==========

MODEL_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "values",
    "providers",
    "flags",
    "departments",
    "modalities",
    "temperature_levels",
    "pricing",
    "reasoning_levels",
    "qualities",
    "voices",
}

MODEL_BASIC_RESOURCES: set[str] = {"names", "descriptions", "flags", "departments"}
MODEL_PROVIDER_RESOURCES: set[str] = {"values", "providers"}
MODEL_FEATURES_RESOURCES: set[str] = {
    "modalities",
    "temperature_levels",
    "pricing",
    "reasoning_levels",
    "qualities",
    "voices",
}
MODEL_GENERAL_RESOURCES: set[str] = MODEL_RESOURCES
