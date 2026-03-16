"""Document permission helpers.

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
    "DOCUMENT_RESOURCES",
    "DOCUMENT_BASIC_RESOURCES",
    "DOCUMENT_CONTENT_RESOURCES",
]


def compute_can_edit(
    user_role: str | None,
    document_department_ids: list[str] | list[UUID] | None,
    active_scenario_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> bool:
    """Unified can_edit logic for get, list, and save views.

    Constraints:
    1. Default documents (no departments) only editable by superadmin
    2. Not linked to active scenarios
    3. User has admin/superadmin role
    4. Non-superadmins must belong to ALL of the document's departments
    """
    # Default documents can only be edited by superadmin
    if not document_department_ids and user_role != "superadmin":
        return False

    # Documents in use by active scenarios cannot be edited
    if active_scenario_count > 0:
        return False

    # Role check
    if user_role not in ("admin", "superadmin"):
        return False

    # Department subset check (when user_department_ids is available)
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and document_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        doc_dept_set = {str(d) for d in document_department_ids}
        if not doc_dept_set.issubset(user_dept_set):
            return False

    return True


def compute_disabled_reason(
    user_role: str | None,
    document_department_ids: list[str] | list[UUID] | None,
    active_scenario_count: int,
    user_department_ids: list[str] | list[UUID] | None = None,
) -> str | None:
    """Compute the reason why editing is disabled, if any.

    Returns None if editing is allowed.
    """
    # Default documents can only be edited by superadmin
    if not document_department_ids and user_role != "superadmin":
        return (
            "This is a default document that cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Documents in use by active scenarios cannot be edited
    if active_scenario_count > 0:
        return (
            "This document is currently in use by scenarios and cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Role check
    if user_role not in ("admin", "superadmin"):
        return (
            "This document cannot be edited. "
            "You can view the details but cannot make changes."
        )

    # Department subset check
    if (
        user_department_ids is not None
        and user_role != "superadmin"
        and document_department_ids
    ):
        user_dept_set = {str(d) for d in user_department_ids}
        doc_dept_set = {str(d) for d in document_department_ids}
        if not doc_dept_set.issubset(user_dept_set):
            return (
                "You don't have access to all departments for this document. "
                "You can view the details but cannot make changes."
            )

    return None


def get_missing_tools(
    names_has_tools: bool,
    show_departments: bool,
    departments_has_tools: bool,
    show_fields: bool,
    fields_has_tools: bool,
    show_uploads: bool,
    uploads_has_tools: bool,
) -> list[str]:
    """Get list of missing required tools."""
    missing = []

    if not names_has_tools:
        missing.append("name")
    if show_departments and not departments_has_tools:
        missing.append("departments")
    if show_fields and not fields_has_tools:
        missing.append("fields")
    if show_uploads and not uploads_has_tools:
        missing.append("uploads")

    return missing


def has_access(
    user_role: str | None,
    user_department_ids: list[UUID] | None,
    document_department_ids: list[UUID] | None,
) -> bool:
    """Check if user has access to view the document.

    Access rules:
    - Superadmin has access to all documents
    - User has access if document has no departments (general document)
    - User has access if they share at least one department with the document
    """
    if user_role == "superadmin":
        return True

    # General documents (no departments) are accessible to all
    if not document_department_ids:
        return True

    # Check department overlap
    if not user_department_ids:
        return False

    user_dept_set = set(user_department_ids)
    doc_dept_set = set(document_department_ids)
    return bool(user_dept_set & doc_dept_set)


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


def compute_show_fields(fields_count: int) -> bool:
    """Determine if fields picker should be shown."""
    return fields_count > 0


def compute_show_uploads() -> bool:
    """Determine if uploads picker should be shown."""
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
    return True


def compute_fields_required() -> bool:
    """Determine if fields is required."""
    return True


def compute_uploads_required() -> bool:
    """Determine if uploads is required."""
    return False


# ========== List Endpoint Permission Functions ==========


def compute_can_delete(
    user_role: str | None,
    document_department_ids: list[str] | list[UUID] | None,
    active_scenario_count: int,
) -> bool:
    """Compute can_delete permission.

    Business logic:
    - Default documents (no departments) only deletable by superadmin
    - Documents linked to active scenarios cannot be deleted
    - Only admins and superadmins can delete
    """
    # Default documents can only be deleted by superadmin
    if not document_department_ids and user_role != "superadmin":
        return False

    # Documents with active scenario links cannot be deleted
    if active_scenario_count > 0:
        return False

    # Only admins and superadmins can delete
    return user_role in ("admin", "superadmin")


def compute_can_duplicate(user_role: str | None) -> bool:
    """Compute can_duplicate permission.

    Business logic:
    - Anyone with edit permissions can duplicate
    """
    return user_role in ("admin", "superadmin")


# ========== Save/Create Endpoint Permission Functions ==========


def compute_can_create(
    user_role: str | None,
    department_ids: list[str] | list[UUID] | None,
) -> bool:
    """Compute permission to create a new document.

    Business logic:
    - Non-superadmins cannot create general objects (empty department_ids)
    - Only admin/superadmin can create documents
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


# ========== Agent Scoring - Document-specific Constants ==========

# Document-specific resource definitions
DOCUMENT_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "flags",
    "departments",
    "fields",
    "uploads",
    "images",
    "texts",
}

# Multi-resource agent definitions for document
DOCUMENT_BASIC_RESOURCES: set[str] = {"names", "descriptions", "flags", "departments"}
DOCUMENT_CONTENT_RESOURCES: set[str] = {"fields", "uploads", "images", "texts"}
DOCUMENT_GENERAL_RESOURCES: set[str] = DOCUMENT_RESOURCES  # All resources

# ========== Domain Metadata - for client-side display in modals ==========

# Domain display metadata (business logic - rarely changes)
DOCUMENT_DOMAIN_METADATA: dict[str, dict[str, str | bool]] = {
    "names": {
        "name": "Name",
        "description": "The display name for this document",
        "icon": "file-text",
    },
    "descriptions": {
        "name": "Description",
        "description": "A brief description of this document",
        "icon": "file-text",
    },
    "flags": {
        "name": "Status",
        "description": "Active/inactive status",
        "icon": "flag",
    },
    "departments": {
        "name": "Departments",
        "description": "Which departments can access this document",
        "icon": "building",
    },
    "fields": {
        "name": "Fields",
        "description": "Custom fields for this document",
        "icon": "form-input",
    },
    "uploads": {
        "name": "Uploads",
        "description": "Files uploaded for this document",
        "icon": "upload",
    },
}


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
) -> list:
    """Build rich domain metadata for client display.

    Delegates to shared build_domain_data with document-specific metadata.
    """
    from app.infra.v5_types import build_domain_data as _build_domain_data

    return _build_domain_data(
        domain_ids, show_flags, required_flags, DOCUMENT_DOMAIN_METADATA
    )
