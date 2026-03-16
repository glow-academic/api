"""Handcrafted types for field artifact endpoints (section-first parity)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.field.create import CreateFieldItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.field_drafts.types import GetFieldDraftResponse
from app.tools.resources.parameters.types import GetParameterResponse


class GetFieldDraftsApiResponse(BaseModel):
    """Response model for field drafts list endpoint."""

    entries: list[GetFieldDraftResponse] | None = Field(None, description="List of field draft entries")


class FieldFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description text")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="UUID of the selected flag option")
    show: bool = Field(True, description="Whether the flag is visible to the client")
    required: bool = Field(False, description="Whether the flag is required")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")


class FieldNameSection(BaseResourceSection):
    resource: object | None = Field(None, description="Currently selected name resource")
    resources: list | None = Field(None, description="Available name resources")


class FieldDescriptionSection(BaseResourceSection):
    resource: object | None = Field(None, description="Currently selected description resource")
    resources: list | None = Field(None, description="Available description resources")


class FieldFlagSection(BaseResourceSection):
    resource: FieldFlagConfig | None = Field(None, description="Currently selected flag config")
    resources: list[FieldFlagConfig] | None = Field(None, description="Available flag configs")


class FieldDepartmentSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned departments")
    resources: list | None = Field(None, description="Available department resources")


class FieldConditionalParameterSection(BaseResourceSection):
    current: list[GetParameterResponse] | None = Field(None, description="Currently assigned conditional parameters")
    resources: list[GetParameterResponse] | None = Field(None, description="Available conditional parameter resources")


class GetFieldApiRequest(BaseModel):
    """Request model for get field endpoint."""

    field_id: UUID | None = Field(None, description="UUID of the field to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")
    descriptions_search: str | None = Field(None, description="Search query for description resources")
    conditional_parameter_search: str | None = Field(None, description="Search query for conditional parameters")
    conditional_parameter_show_selected: bool | None = Field(None, description="Whether to show only selected parameters")


class GetFieldApiResponse(BaseModel):
    """Section-first client response for get field endpoint."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    field_exists: bool | None = Field(None, description="Whether the field exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this field")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")

    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate button")

    names: FieldNameSection | None = Field(None, description="Name section with resources")
    descriptions: FieldDescriptionSection | None = Field(None, description="Description section with resources")
    flags: FieldFlagSection | None = Field(None, description="Flag section with configs")
    departments: FieldDepartmentSection | None = Field(None, description="Department section with resources")
    conditional_parameters: FieldConditionalParameterSection | None = Field(None, description="Conditional parameter section")


# ========== List Endpoint Types ==========


class ListFieldApiField(BaseModel):
    field_id: UUID | None = Field(None, description="Unique field identifier")
    name: str | None = Field(None, description="Field display name")
    description: str | None = Field(None, description="Field description text")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Associated conditional parameter UUIDs")
    persona_ids: list[UUID] | None = Field(None, description="Associated persona UUIDs")
    is_inactive: bool | None = Field(None, description="Whether the field is inactive")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this field")
    can_duplicate: bool | None = Field(None, description="Whether the actor can duplicate this field")
    can_delete: bool | None = Field(None, description="Whether the actor can delete this field")
    updated_at: datetime | None = Field(None, description="Timestamp of last update")


class ListFieldApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the acting user")
    fields: list[ListFieldApiField] | None = Field(None, description="List of field items")
    parameter_filter: ListFilterSection | None = Field(None, description="Filter options for parameters")
    persona_filter: ListFilterSection | None = Field(None, description="Filter options for personas")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments")
    total_count: int | None = Field(None, description="Total number of fields")


# ========== Shared Create/Update Types ==========


class FieldFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class FieldResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    field_id: UUID | None = Field(None, description="UUID of the created or updated field")
    message: str = Field(..., description="Result message")
    errors: list[FieldFieldError] | None = Field(None, description="Per-field validation errors")


# ========== Create Endpoint Types ==========


class CreateFieldApiRequest(BaseModel):
    """Request model for bulk create field endpoint."""

    fields: list[CreateFieldItem] = Field(..., description="List of fields to create")


class CreateFieldApiResponse(BaseModel):
    """Response model for bulk create field endpoint."""

    results: list[FieldResultItem] = Field(..., description="Per-item creation results")


# ========== Update Endpoint Types ==========


class UpdateFieldItem(BaseModel):
    """Single field item for update — field_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    field_id: UUID = Field(..., description="UUID of the field to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    # Optional single-select — provide ID only
    flag_id: UUID | None = Field(None, description="UUID of the flag option")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Conditional parameter UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Related field UUIDs")


class UpdateFieldApiRequest(BaseModel):
    """Request model for bulk update field endpoint."""

    fields: list[UpdateFieldItem] = Field(..., description="List of fields to update")


class UpdateFieldApiResponse(BaseModel):
    """Response model for bulk update field endpoint."""

    results: list[FieldResultItem] = Field(..., description="Per-item update results")


class SaveFieldFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchFieldDraftApiRequest(BaseModel):
    """Request model for new-style field draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_id, department_ids, conditional_parameter_ids

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
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Conditional parameter UUIDs")


class FieldDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    flag_id: UUID | None = Field(None, description="Resolved flag option UUID")
    department_ids: list[UUID] = Field(..., description="Assigned department UUIDs")
    conditional_parameter_ids: list[UUID] = Field(..., description="Assigned conditional parameter UUIDs")


class PatchFieldDraftApiResponse(BaseModel):
    """Response model for new-style field draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Result message")
    form_state: FieldDraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Delete Endpoint Types ==========


class DeleteFieldApiRequest(BaseModel):
    """Request model for bulk delete field endpoint."""

    field_ids: list[UUID] = Field(..., description="UUIDs of fields to delete")


class DeleteFieldResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    field_id: UUID = Field(..., description="UUID of the deleted field")
    message: str = Field(..., description="Result message")


class DeleteFieldApiResponse(BaseModel):
    """Response model for bulk delete field endpoint."""

    results: list[DeleteFieldResult] = Field(..., description="Per-item deletion results")


# ========== Duplicate Endpoint Types ==========


class DuplicateFieldApiRequest(BaseModel):
    field_id: UUID = Field(..., description="UUID of the field to duplicate")


class DuplicateFieldApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    field_id: UUID = Field(..., description="UUID of the newly created field")
    message: str = Field(..., description="Result message")


# ========== Export Endpoint Types ==========


class ExportFieldApiRequest(BaseModel):
    """Request model for field export."""

    field_id: UUID | None = Field(None, description="UUID of the field to export")


class ExportFieldApiResponse(BaseModel):
    """Response model for export field endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")
