"""Eval permission helpers.

Pure Python business logic for eval permissions, UI flags, and access control.
Used by the composable infra architecture GET endpoint.
"""

from uuid import UUID


def compute_can_edit(
    user_role: str | None,
) -> bool:
    """Unified can_edit logic for both get and list views.

    Constraints:
    1. User has superadmin role
    """
    return user_role == "superadmin"


def compute_disabled_reason(
    user_role: str | None,
) -> str | None:
    """Compute the reason why editing is disabled, if any."""
    if user_role != "superadmin":
        return (
            "This eval cannot be edited. "
            "You can view the details but cannot make changes."
        )

    return None


def has_access(
    user_role: str | None,
    user_department_ids: list[UUID] | None,
    eval_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the eval.

    Access rules:
    - Superadmin has access to all evals
    - User has access if eval has no departments (general eval)
    - User has access if they share at least one department with the eval
    """
    if user_role == "superadmin":
        return True

    # General evals (no departments) are accessible to all
    if not eval_department_ids:
        return True

    # Check department overlap
    if not user_department_ids:
        return False

    user_dept_set = set(user_department_ids)
    eval_dept_set = set(eval_department_ids)
    return bool(user_dept_set & eval_dept_set)


# ========== Show Functions ==========


def compute_show_name(names_has_tools: bool) -> bool:
    """Determine if name picker should be shown."""
    return names_has_tools


def compute_show_description() -> bool:
    """Determine if description picker should be shown."""
    return True


def compute_show_active_flag() -> bool:
    """Determine if active flag toggle should be shown."""
    return True


def compute_show_dynamic_flag() -> bool:
    """Determine if dynamic flag toggle should be shown."""
    return True


def compute_show_groups_flag() -> bool:
    """Determine if groups flag toggle should be shown."""
    return True


def compute_show_departments(departments_count: int) -> bool:
    """Determine if departments picker should be shown."""
    return departments_count > 0


def compute_show_models(models_count: int) -> bool:
    """Determine if models picker should be shown."""
    return models_count > 0


def compute_show_model_flags(model_flags_count: int) -> bool:
    """Determine if model flags picker should be shown."""
    return model_flags_count > 0


def compute_show_model_rubrics(model_rubrics_count: int) -> bool:
    """Determine if model rubrics picker should be shown."""
    return model_rubrics_count > 0


def compute_show_model_positions(model_positions_count: int) -> bool:
    """Determine if model positions picker should be shown."""
    return model_positions_count > 0


# ========== Required Functions ==========


def compute_name_required() -> bool:
    """Determine if name is required."""
    return True


def compute_description_required() -> bool:
    """Determine if description is required."""
    return False


def compute_active_flag_required() -> bool:
    """Determine if active flag is required."""
    return False


def compute_dynamic_flag_required() -> bool:
    """Determine if dynamic flag is required."""
    return False


def compute_groups_flag_required() -> bool:
    """Determine if groups flag is required."""
    return False


def compute_departments_required(show_departments: bool) -> bool:
    """Determine if departments is required."""
    return show_departments


def compute_models_required() -> bool:
    """Determine if models is required."""
    return False


def compute_model_flags_required() -> bool:
    """Determine if model flags is required."""
    return False


def compute_model_rubrics_required() -> bool:
    """Determine if model rubrics is required."""
    return False


def compute_model_positions_required() -> bool:
    """Determine if model positions is required."""
    return False


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    user_role: str | None,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Only superadmins can delete (no parent check needed)
    """
    return user_role == "superadmin"


def compute_can_duplicate(user_role: str | None) -> bool:
    """Compute can_duplicate permission."""
    return user_role == "superadmin"


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    user_role: str | None,
) -> bool:
    """Compute permission to create a new eval."""
    return user_role == "superadmin"


# ========== Draft Endpoint Permission Functions ==========


def compute_can_draft(user_role: str | None) -> bool:
    """Compute permission to create or update a draft."""
    return user_role == "superadmin"


# ========== Agent Scoring - Eval-specific Constants ==========

EVAL_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
    "models",
    "model_flags",
    "model_rubrics",
    "model_positions",
}

EVAL_BASIC_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
}

EVAL_MODEL_RESOURCES: set[str] = {
    "models",
    "model_flags",
    "model_rubrics",
    "model_positions",
}

# ========== Domain Metadata - for client-side display in modals ==========

EVAL_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "The display name for this eval",
        "icon": "clipboard-check",
    },
    "descriptions": {
        "name": "Description",
        "description": "A brief description of this eval's purpose",
        "icon": "file-text",
    },
    "flags": {
        "name": "Status",
        "description": "Active/inactive and configuration flags",
        "icon": "flag",
    },
    "departments": {
        "name": "Departments",
        "description": "Which departments can access this eval",
        "icon": "building",
    },
    "models": {
        "name": "Models",
        "description": "Models used in this eval",
        "icon": "cpu",
    },
    "model_flags": {
        "name": "Model Flags",
        "description": "Flag configurations per model",
        "icon": "flag",
    },
    "model_rubrics": {
        "name": "Model Rubrics",
        "description": "Rubric assignments per model",
        "icon": "list-checks",
    },
    "model_positions": {
        "name": "Model Positions",
        "description": "Position assignments per model",
        "icon": "move",
    },
}


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
) -> list:
    """Build rich domain metadata for client display.

    Delegates to shared build_domain_data with eval-specific metadata.
    """
    from app.infra.v5_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, EVAL_DOMAIN_METADATA
    )
