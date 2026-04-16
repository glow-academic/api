"""Handcrafted types for field artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.field_drafts.types import GetFieldDraftResponse


class GetFieldDraftsApiResponse(BaseModel):
    """Response model for field drafts list endpoint."""

    entries: list[GetFieldDraftResponse] | None = Field(None, description="List of field draft entries")


class FieldNameResource(BaseModel):
    """Name resource for field."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class FieldDescriptionResource(BaseModel):
    """Description resource for field."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class FieldDepartmentResource(BaseModel):
    """Department resource for field."""

    department_id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class FieldConditionalParameterResource(BaseModel):
    """Conditional parameter resource for field."""

    parameter_id: UUID | None = Field(None, description="Parameter identifier")
    name: str | None = Field(None, description="Parameter display name")
    description: str | None = Field(None, description="Parameter description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


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
        description="Parameter group IDs to filter by where relevant",
    )


class GetFieldApiRequest(BaseModel):
    """Request model for get field endpoint."""

    id: UUID | None = Field(None, description="Field UUID to retrieve")
    field_id: UUID | None = Field(None, description="UUID of the field to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    conditional_parameters: SectionFilter | None = Field(None, description="Filter options for conditional parameters section")
    descriptions_search: str | None = Field(None, description="Search query for description resources")
    conditional_parameter_search: str | None = Field(None, description="Search query for conditional parameters")
    conditional_parameter_show_selected: bool | None = Field(None, description="Whether to show only selected parameters")


class GetFieldApiResponse(BaseModel):
    """Canonical flat composed response for the field editor."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    field_exists: bool | None = Field(None, description="Whether the field exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this field")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")
    show_ai_generate: bool | None = Field(None, description="Whether to show AI generate button anywhere")
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate button")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[FieldNameResource] | None = Field(None, description="Name resources")
    descriptions: list[FieldDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[FieldFlagConfig] | None = Field(None, description="Flag configs")
    departments: list[FieldDepartmentResource] | None = Field(None, description="Department resources")
    conditional_parameters: list[FieldConditionalParameterResource] | None = Field(None, description="Conditional parameter resources")


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


class CreateFieldItem(ScopedItem):
    """Single field item for create — no field_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "active_flag": "flags",
        "active_flag_id": "flags",
        "flag_id": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "conditional_parameter_ids": "conditional_parameters",
        "field_ids": "fields",
    }

    id: UUID | None = Field(None, description="Optional preset UUID for the new field")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    # Active flag
    active_flag: bool | None = Field(None, description="Whether this field is active")
    active_flag_id: UUID | None = Field(None, description="Active flag resource UUID")
    # Optional single-select — provide ID only
    flag_id: UUID | None = Field(None, description="UUID of the flag option")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Conditional parameter UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Related field UUIDs")


class CreateFieldApiRequest(BaseModel):
    """Request model for bulk create field endpoint."""

    fields: list[CreateFieldItem] = Field(..., description="List of fields to create")


class CreateFieldApiResponse(BaseModel):
    """Response model for bulk create field endpoint."""

    results: list[FieldResultItem] = Field(..., description="Per-item creation results")


# ========== Update Endpoint Types ==========


class UpdateFieldItem(ScopedItem):
    """Single field item for update — field_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateFieldItem.RESOURCE_TYPE_MAP

    field_id: UUID = Field(..., description="UUID of the field to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    # Active flag
    active_flag: bool | None = Field(None, description="Whether this field is active")
    active_flag_id: UUID | None = Field(None, description="Active flag resource UUID")
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


class PatchFieldDraftApiRequest(ScopedItem):
    """Request model for new-style field draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_id, department_ids, conditional_parameter_ids

    Client always sends full state (append-only — each write is a new snapshot).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "active_flag": "flags",
        "active_flag_id": "flags",
        "flag_id": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "conditional_parameters": "conditional_parameters",
        "conditional_parameter_ids": "conditional_parameters",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to update")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to resolve or create")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    active_flag: bool | None = Field(None, description="Whether the field is active")
    active_flag_id: UUID | None = Field(None, description="UUID of the active flag resource")
    # Non-creatable — ID-only
    flag_id: UUID | None = Field(None, description="UUID of the flag option")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Conditional parameter UUIDs")
    conditional_parameters: list[str] | None = Field(None, description="Conditional parameter names to resolve")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep pending where supported")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack or retry")
    accept: bool = Field(True, description="Accept or reject dormant state")


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    name: str | None = Field(None, description="Echoed name value")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    description: str | None = Field(None, description="Echoed description value")
    flag_id: UUID | None = Field(None, description="Resolved flag option UUID")
    active_flag_id: UUID | None = Field(None, description="Resolved active flag option UUID")
    department_ids: list[UUID] = Field(..., description="Assigned department UUIDs")
    conditional_parameter_ids: list[UUID] = Field(..., description="Assigned conditional parameter UUIDs")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


FieldDraftFormState = DraftFormState


class PatchFieldDraftApiResponse(BaseModel):
    """Response model for new-style field draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    idempotency_key: UUID = Field(..., description="Idempotency key for this draft operation")
    message: str = Field(..., description="Result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


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


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsFieldApiRequest(BaseModel):
    """Request model for field generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsFieldListItem(BaseModel):
    """Single generation group in the field generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsFieldApiResponse(BaseModel):
    """Response model for field generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsFieldListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemFieldApiRequest(BaseModel):
    """Request model for field problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")


class ProblemFieldApiResponse(BaseModel):
    """Response model for field problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
