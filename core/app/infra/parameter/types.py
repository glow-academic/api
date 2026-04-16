"""Handcrafted types for parameter artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.parameter_drafts.types import GetParameterDraftResponse

# ---------------------------------------------------------------------------
# Handcrafted resource types (replaces Q types from app.sql.types)
# ---------------------------------------------------------------------------


class ParameterNameResource(BaseModel):
    """Name resource for parameter."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class ParameterDescriptionResource(BaseModel):
    """Description resource for parameter."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class ParameterDepartmentResource(BaseModel):
    """Department resource for parameter."""

    department_id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class ParameterFieldResource(BaseModel):
    """Parameter field resource for parameter."""

    id: UUID | None = Field(None, description="Unique identifier")
    field_id: UUID | None = Field(None, description="Associated field identifier")
    parameter_id: UUID | None = Field(None, description="Parent parameter identifier")
    name: str | None = Field(None, description="Field display name")
    description: str | None = Field(None, description="Field description")
    conditional_parameter_id: UUID | None = Field(None, description="Conditional parameter identifier")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class ParameterDraftEntry(BaseModel):
    """Draft entry for parameter."""

    id: UUID | None = Field(None, description="Draft entry identifier")

    created_at: datetime | None = Field(None, description="Timestamp when draft was created")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether this is an MCP draft")
    active: bool | None = Field(None, description="Whether this draft is active")
    group_id: UUID | None = Field(None, description="Group identifier")
    session_id: UUID | None = Field(None, description="Session identifier")
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    description_ids: list[UUID] | None = Field(None, description="Description resource identifiers")
    field_ids: list[UUID] | None = Field(None, description="Field identifiers")
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    name_ids: list[UUID] | None = Field(None, description="Name resource identifiers")
    profile_ids: list[UUID] | None = Field(None, description="Profile identifiers")


class ParameterFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="Option ID to use when enabling")
    show: bool = Field(True, description="Whether to display this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this flag was AI-generated")
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
        description="Parameter group IDs to filter by (parameter_fields section only)",
    )


# ---------------------------------------------------------------------------
# GET endpoint types
# ---------------------------------------------------------------------------


class GetParameterApiRequest(BaseModel):
    """Request model for get parameter endpoint."""

    id: UUID | None = Field(None, description="Parameter unique identifier")
    parameter_id: UUID | None = Field(None, description="Legacy alias for parameter unique identifier")
    draft_id: UUID | None = Field(None, description="Draft unique identifier")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    parameter_fields: SectionFilter | None = Field(None, description="Filter options for parameter fields section")
    fields: SectionFilter | None = Field(None, description="Legacy alias for parameter_fields")


class GetParameterApiResponse(BaseModel):
    """Canonical flat composed response for the parameter editor."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    parameter_exists: bool | None = Field(None, description="Whether the parameter exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    group_id: UUID | None = Field(None, description="Group identifier for the parameter")
    show_ai_generate: bool | None = Field(None, description="Show AI generate if any resource supports it")
    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    fields_step_show_ai_generate: bool | None = Field(None, description="Show AI generate for fields step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[ParameterNameResource] | None = Field(None, description="Name resources")
    descriptions: list[ParameterDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[ParameterFlagConfig] | None = Field(None, description="Flag configs")
    departments: list[ParameterDepartmentResource] | None = Field(None, description="Department resources")
    parameter_fields: list[ParameterFieldResource] | None = Field(None, description="Parameter field resources")


class GetParameterDraftsApiResponse(BaseModel):
    """Response model for parameter drafts list endpoint."""

    entries: list[GetParameterDraftResponse] | None = Field(None, description="List of parameter draft entries")


# ========== List Endpoint Types ==========


class ListParameterApiParameter(BaseModel):
    parameter_id: UUID | None = Field(None, description="Parameter unique identifier")
    name: str | None = Field(None, description="Display name of the parameter")
    description: str | None = Field(None, description="Parameter description text")
    active: bool | None = Field(None, description="Whether this parameter is currently active")
    department_ids: list[str] | None = Field(None, description="Associated department identifiers")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario identifiers")
    document_ids: list[UUID] | None = Field(None, description="Associated document identifiers")
    num_items: int | None = Field(None, description="Number of items in this parameter")
    sample_items: list[str] | None = Field(None, description="Sample items for preview")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    updated_at: datetime | None = Field(None, description="Timestamp of last update")


class ListParameterApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    parameters: list[ListParameterApiParameter] | None = Field(None, description="List of parameter entries")
    scenario_filter: ListFilterSection | None = Field(None, description="Scenario filter options")
    field_filter: ListFilterSection | None = Field(None, description="Field filter options")
    department_filter: ListFilterSection | None = Field(None, description="Department filter options")
    total_count: int | None = Field(None, description="Total number of parameters")


# ========== Shared Create/Update Types ==========


class ParameterFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class ParameterResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    parameter_id: UUID | None = Field(None, description="Parameter unique identifier")
    message: str = Field(..., description="Result message")
    errors: list[ParameterFieldError] | None = Field(None, description="List of field-level errors")


# ========== Create Endpoint Types ==========


class CreateParameterItem(ScopedItem):
    """Single parameter item for create — no parameter_id."""

    id: UUID | None = Field(None, description="Optional pre-assigned identifier")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    field_ids: list[UUID] | None = Field(None, description="Field identifiers")
    persona_parameter: bool | None = Field(None, description="Show on persona edit page")
    document_parameter: bool | None = Field(None, description="Show on document edit page")
    scenario_parameter: bool | None = Field(None, description="Show on scenario edit page")
    video_parameter: bool | None = Field(None, description="Show on video edit page")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "department_ids": "departments",
        "departments": "departments",
        "flag_ids": "flags",
        "field_ids": "fields",
    }


class CreateParameterApiRequest(BaseModel):
    """Request model for bulk create parameter endpoint."""

    parameters: list[CreateParameterItem] = Field(..., description="List of parameters to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateParameterApiResponse(BaseModel):
    """Response model for bulk create parameter endpoint."""

    results: list[ParameterResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateParameterItem(ScopedItem):
    """Single parameter item for update — parameter_id required, all fields optional."""

    parameter_id: UUID = Field(..., description="Target parameter identifier to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    field_ids: list[UUID] | None = Field(None, description="Field identifiers")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateParameterItem.RESOURCE_TYPE_MAP


class UpdateParameterApiRequest(BaseModel):
    """Request model for bulk update parameter endpoint."""

    parameters: list[UpdateParameterItem] = Field(..., description="List of parameters to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateParameterApiResponse(BaseModel):
    """Response model for bulk update parameter endpoint."""

    results: list[ParameterResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveParameterFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchParameterDraftApiRequest(ScopedItem):
    """Request model for new-style parameter draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_ids, department_ids, field_ids

    Client always sends full state (append-only — each write is a new snapshot).
    """

    draft_id: UUID | None = Field(None, description="Existing draft ID to update")
    input_draft_id: UUID | None = Field(None, description="Legacy alias for existing draft ID to update")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="Name resource identifier")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="Description resource identifier")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    field_ids: list[UUID] | None = Field(None, description="Field identifiers")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    parameter_fields: list[str] | None = Field(None, description="Parameter field names to resolve")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep pending where supported")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack or retry")
    accept: bool = Field(True, description="Accept or reject dormant state")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "field_ids": "parameter_fields",
        "parameter_fields": "parameter_fields",
    }


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource identifier")
    name: str | None = Field(None, description="Echoed name value")
    description_id: UUID | None = Field(None, description="Resolved description resource identifier")
    description: str | None = Field(None, description="Echoed description value")
    flag_ids: list[UUID] = Field(..., description="Flag option identifiers")
    department_ids: list[UUID] = Field(..., description="Department identifiers")
    field_ids: list[UUID] = Field(..., description="Field identifiers")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


ParameterDraftFormState = DraftFormState


class PatchParameterDraftApiResponse(BaseModel):
    """Response model for new-style parameter draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="Draft unique identifier")
    idempotency_key: UUID = Field(..., description="Idempotency key for this draft operation")
    message: str = Field(..., description="Result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Delete Endpoint Types ==========


class DeleteParameterApiRequest(BaseModel):
    """Request model for bulk delete parameter endpoint."""

    parameter_ids: list[UUID] = Field(..., description="List of parameter IDs to delete")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm deletion) or reject (restore). Only meaningful with idempotency_key")


class DeleteParameterResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    parameter_id: UUID = Field(..., description="Deleted parameter identifier")
    message: str = Field(..., description="Result message")


class DeleteParameterApiResponse(BaseModel):
    """Response model for bulk delete parameter endpoint."""

    results: list[DeleteParameterResult] = Field(..., description="List of deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Duplicate Endpoint Types ==========


class DuplicateParameterApiRequest(BaseModel):
    parameter_id: UUID = Field(..., description="Parameter identifier to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateParameterApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    parameter_id: UUID = Field(..., description="New duplicated parameter identifier")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Export Endpoint Types ==========


class ExportParameterApiRequest(BaseModel):
    """Request model for parameter export."""

    parameter_id: UUID | None = Field(None, description="Parameter identifier to export")


class ExportParameterApiResponse(BaseModel):
    """Response model for export parameter endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsParameterApiRequest(BaseModel):
    """Request model for parameter generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsParameterListItem(BaseModel):
    """Single generation group in the parameter generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsParameterApiResponse(BaseModel):
    """Response model for parameter generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsParameterListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemParameterApiRequest(BaseModel):
    """Request model for parameter problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemParameterApiResponse(BaseModel):
    """Response model for parameter problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
