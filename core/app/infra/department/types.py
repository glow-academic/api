"""Handcrafted types for department artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from typing import ClassVar

from pydantic import BaseModel, Field

from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.department_drafts.types import (
    GetDepartmentDraftResponse,
)


class GetDepartmentDraftsApiResponse(BaseModel):
    """Response model for department drafts list endpoint."""

    entries: list[GetDepartmentDraftResponse] | None = Field(None, description="List of department draft entries")


class DepartmentNameResource(BaseModel):
    """Name resource for department."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DepartmentDescriptionResource(BaseModel):
    """Description resource for department."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DepartmentFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'department_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DepartmentSettingResource(BaseModel):
    """Setting resource for department."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Setting display name")
    description: str | None = Field(None, description="Setting description")
    department_ids: list[UUID] = Field(default_factory=list, description="Associated department identifiers")
    provider_key_ids: list[UUID] = Field(default_factory=list, description="Associated provider key identifiers")
    auth_ids: list[UUID] = Field(default_factory=list, description="Associated auth identifiers")
    system_ids: list[UUID] = Field(default_factory=list, description="Associated system identifiers")
    active: bool | None = Field(None, description="Whether this setting is active")
    mcp: bool | None = Field(None, description="Whether this setting used MCP")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class SectionFilter(BaseModel):
    """Per-section filter options for GET requests."""

    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")
    parameter_ids: list[str] | None = Field(
        None,
        description="Reserved for compatibility with shared filter parsing",
    )


class GetDepartmentApiRequest(BaseModel):
    """Request model for get department endpoint."""

    id: UUID | None = Field(None, description="Department UUID to retrieve")
    department_id: UUID | None = Field(None, description="Legacy department UUID to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    settings: SectionFilter | None = Field(None, description="Filter options for settings section")


class GetDepartmentApiResponse(BaseModel):
    """Canonical flat composed response for the department editor."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    department_exists: bool | None = Field(None, description="Whether the department exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this department")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")
    show_ai_generate: bool | None = Field(None, description="Whether to show AI generate anywhere")
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for basic sections")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[DepartmentNameResource] | None = Field(None, description="Name resources")
    descriptions: list[DepartmentDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[DepartmentFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    settings: list[DepartmentSettingResource] | None = Field(None, description="Setting resources")


# ========== Shared Create/Update Types ==========


class DepartmentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class DepartmentResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    department_id: UUID | None = Field(None, description="UUID of the created or updated department")
    message: str = Field(..., description="Result message")
    errors: list[DepartmentFieldError] | None = Field(None, description="Per-field validation errors")


# ========== Create Endpoint Types ==========


class CreateDepartmentItem(ScopedItem):
    """Single department item for create — no department_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "flag_ids": "flags",
        "active": "flags",
        "settings_ids": "settings",
        "department_ids": "departments",
    }

    id: UUID | None = Field(None, description="Optional preset UUID for the new department artifact")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the departments_resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    # Canonical multi-select flag ids + denormalized boolean for department_active.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized department_active flag state; resolved to a flag_ids entry server-side")
    # ID-only fields
    settings_ids: list[UUID] | None = Field(None, description="Setting UUIDs to assign")
    department_ids: list[UUID] | None = Field(None, description="Sub-department UUIDs to assign")


class CreateDepartmentApiRequest(BaseModel):
    """Request model for bulk create department endpoint."""

    departments: list[CreateDepartmentItem] = Field(..., description="List of departments to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateDepartmentApiResponse(BaseModel):
    """Response model for bulk create department endpoint."""

    results: list[DepartmentResultItem] = Field(..., description="Per-item creation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateDepartmentItem(ScopedItem):
    """Single department item for update — department_id required, all fields optional."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateDepartmentItem.RESOURCE_TYPE_MAP

    id: UUID = Field(..., description="UUID of the department to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    # Canonical multi-select flag ids + denormalized boolean for department_active.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized department_active flag state; resolved to a flag_ids entry server-side")
    # ID-only fields
    settings_ids: list[UUID] | None = Field(None, description="Setting UUIDs to assign")
    department_ids: list[UUID] | None = Field(None, description="Sub-department UUIDs to assign")


class UpdateDepartmentApiRequest(BaseModel):
    """Request model for bulk update department endpoint."""

    departments: list[UpdateDepartmentItem] = Field(..., description="List of departments to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateDepartmentApiResponse(BaseModel):
    """Response model for bulk update department endpoint."""

    results: list[DepartmentResultItem] = Field(..., description="Per-item update results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveDepartmentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class DeleteDepartmentApiRequest(BaseModel):
    """Request model for bulk delete department endpoint."""

    department_ids: list[UUID] = Field(..., description="UUIDs of departments to delete")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteDepartmentResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    department_id: UUID = Field(..., description="UUID of the deleted department")
    message: str = Field(..., description="Result message")


class DeleteDepartmentApiResponse(BaseModel):
    """Response model for bulk delete department endpoint."""

    results: list[DeleteDepartmentResult] = Field(..., description="Per-item deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateDepartmentApiRequest(BaseModel):
    department_id: UUID = Field(..., description="UUID of the department to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateDepartmentApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    department_id: UUID = Field(..., description="UUID of the newly created department")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchDepartmentDraftApiRequest(ScopedItem):
    """Request model for canonical department draft endpoint."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "settings": "settings",
        "setting_ids": "settings",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to update")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to resolve or create")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized department_active flag state; resolved to a flag_ids entry server-side")
    settings: list[str] | None = Field(None, description="Setting names to resolve")
    setting_ids: list[UUID] | None = Field(None, description="Setting UUIDs to assign")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep pending where supported")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack or retry")
    accept: bool = Field(True, description="Accept or reject dormant state")


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    name: str | None = Field(None, description="Echoed name value")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    description: str | None = Field(None, description="Echoed description value")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed department_active flag state")
    setting_ids: list[UUID] = Field(default_factory=list, description="Assigned setting UUIDs")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


DepartmentDraftFormState = DraftFormState


class PatchDepartmentDraftApiResponse(BaseModel):
    """Response model for new-style department draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    idempotency_key: UUID | None = Field(None, description="Idempotency key for this draft operation")
    message: str = Field(..., description="Result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Export Endpoint Types ==========


class ExportDepartmentApiRequest(BaseModel):
    """Request model for department export."""

    department_id: UUID | None = Field(None, description="UUID of the department to export")


class ExportDepartmentApiResponse(BaseModel):
    """Response model for export department endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


class ListDepartmentApiDepartment(BaseModel):
    department_id: UUID | None = Field(None, description="Unique department identifier")
    name: str | None = Field(None, description="Department display name")
    description: str | None = Field(None, description="Department description text")
    staff_count: int | None = Field(None, description="Number of staff in the department")
    is_inactive: bool | None = Field(None, description="Whether the department is inactive")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this department")
    can_duplicate: bool | None = Field(None, description="Whether the actor can duplicate this department")
    can_delete: bool | None = Field(None, description="Whether the actor can delete this department")
    updated_at: datetime | None = Field(None, description="Timestamp of last update")


class ListDepartmentApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the acting user")
    departments: list[ListDepartmentApiDepartment] | None = Field(None, description="List of department items")
    total_count: int | None = Field(None, description="Total number of departments")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsDepartmentApiRequest(BaseModel):
    """Request model for department generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsDepartmentListItem(BaseModel):
    """Single generation group in the department generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsDepartmentApiResponse(BaseModel):
    """Response model for department generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsDepartmentListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemDepartmentApiRequest(BaseModel):
    """Request model for department problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemDepartmentApiResponse(BaseModel):
    """Response model for department problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
