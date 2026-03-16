"""Handcrafted types for department artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.department.create import CreateDepartmentItem
from app.infra.v5_types import BaseResourceSection
from app.tools.entries.department_drafts.types import (
    GetDepartmentDraftResponse,
)


class GetDepartmentDraftsApiResponse(BaseModel):
    """Response model for department drafts list endpoint."""

    entries: list[GetDepartmentDraftResponse] | None = Field(None, description="List of department draft entries")


class DepartmentFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description text")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="UUID of the selected flag option")
    show: bool = Field(True, description="Whether the flag is visible to the client")
    required: bool = Field(False, description="Whether the flag is required")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")


class DepartmentNameSection(BaseResourceSection):
    resource: object | None = Field(None, description="Currently selected name resource")
    resources: list | None = Field(None, description="Available name resources")


class DepartmentDescriptionSection(BaseResourceSection):
    resource: object | None = Field(None, description="Currently selected description resource")
    resources: list | None = Field(None, description="Available description resources")


class DepartmentFlagSection(BaseResourceSection):
    current: list[DepartmentFlagConfig] | None = Field(None, description="Currently assigned flag configs")
    resources: list[DepartmentFlagConfig] | None = Field(None, description="Available flag configs")


class DepartmentSettingSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned settings")
    resources: list | None = Field(None, description="Available setting resources")


class GetDepartmentApiRequest(BaseModel):
    department_id: UUID | None = Field(None, description="UUID of the department to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")


class GetDepartmentApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the acting user")
    department_exists: bool | None = Field(None, description="Whether the department exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this department")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")

    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate button")

    names: DepartmentNameSection | None = Field(None, description="Name section with resources")
    descriptions: DepartmentDescriptionSection | None = Field(None, description="Description section with resources")
    flags: DepartmentFlagSection | None = Field(None, description="Flag section with configs")
    settings: DepartmentSettingSection | None = Field(None, description="Setting section with resources")


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


class CreateDepartmentApiRequest(BaseModel):
    """Request model for bulk create department endpoint."""

    departments: list[CreateDepartmentItem] = Field(..., description="List of departments to create")


class CreateDepartmentApiResponse(BaseModel):
    """Response model for bulk create department endpoint."""

    results: list[DepartmentResultItem] = Field(..., description="Per-item creation results")


# ========== Update Endpoint Types ==========


class UpdateDepartmentItem(BaseModel):
    """Single department item for update — department_id required, all fields optional."""

    department_id: UUID = Field(..., description="UUID of the department to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    active_flag_id: UUID | None = Field(None, description="UUID of the active flag option")
    active_flag: bool | None = Field(None, description="Whether the department is active")
    # ID-only fields
    settings_ids: list[UUID] | None = Field(None, description="Setting UUIDs to assign")
    department_ids: list[UUID] | None = Field(None, description="Sub-department UUIDs to assign")


class UpdateDepartmentApiRequest(BaseModel):
    """Request model for bulk update department endpoint."""

    departments: list[UpdateDepartmentItem] = Field(..., description="List of departments to update")


class UpdateDepartmentApiResponse(BaseModel):
    """Response model for bulk update department endpoint."""

    results: list[DepartmentResultItem] = Field(..., description="Per-item update results")


class SaveDepartmentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class DeleteDepartmentApiRequest(BaseModel):
    """Request model for bulk delete department endpoint."""

    department_ids: list[UUID] = Field(..., description="UUIDs of departments to delete")


class DeleteDepartmentResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    department_id: UUID = Field(..., description="UUID of the deleted department")
    message: str = Field(..., description="Result message")


class DeleteDepartmentApiResponse(BaseModel):
    """Response model for bulk delete department endpoint."""

    results: list[DeleteDepartmentResult] = Field(..., description="Per-item deletion results")


class DuplicateDepartmentApiRequest(BaseModel):
    department_id: UUID = Field(..., description="UUID of the department to duplicate")


class DuplicateDepartmentApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    department_id: UUID = Field(..., description="UUID of the newly created department")
    message: str = Field(..., description="Result message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchDepartmentDraftApiRequest(BaseModel):
    """Request model for new-style department draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_id, setting_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    expected_version: int = Field(0, description="Expected draft version for optimistic locking")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to resolve or create")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    # Non-creatable — ID-only
    flag_id: UUID | None = Field(None, description="UUID of the flag option")
    setting_ids: list[UUID] | None = Field(None, description="Setting UUIDs to assign")


class DepartmentDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    flag_id: UUID | None = Field(None, description="Resolved flag option UUID")
    setting_ids: list[UUID] = Field(..., description="Assigned setting UUIDs")


class PatchDepartmentDraftApiResponse(BaseModel):
    """Response model for new-style department draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Result message")
    form_state: DepartmentDraftFormState | None = Field(None, description="Server-authoritative form state")


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
