"""Handcrafted types for parameter artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.parameter.create import CreateParameterItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.parameter_drafts.types import GetParameterDraftResponse

# ---------------------------------------------------------------------------
# Handcrafted resource types (replaces Q types from app.sql.types)
# ---------------------------------------------------------------------------


class ParameterNameResource(BaseModel):
    """Name resource for parameter."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class ParameterDescriptionResource(BaseModel):
    """Description resource for parameter."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class ParameterDepartmentResource(BaseModel):
    """Department resource for parameter."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class ParameterFieldResource(BaseModel):
    """Parameter field resource for parameter."""

    id: UUID | None = Field(None, description="Unique identifier")
    field_id: UUID | None = Field(None, description="Associated field identifier")
    parameter_id: UUID | None = Field(None, description="Parent parameter identifier")
    name: str | None = Field(None, description="Field display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class ParameterDraftEntry(BaseModel):
    """Draft entry for parameter."""

    id: UUID | None = Field(None, description="Draft entry identifier")
    version: int | None = Field(None, description="Draft version number")
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


# ---------------------------------------------------------------------------
# Section types
# ---------------------------------------------------------------------------


class ParameterNameSection(BaseResourceSection):
    resource: ParameterNameResource | None = Field(None, description="Currently selected name resource")
    resources: list[ParameterNameResource] | None = Field(None, description="Available name resources")


class ParameterDescriptionSection(BaseResourceSection):
    resource: ParameterDescriptionResource | None = Field(None, description="Currently selected description resource")
    resources: list[ParameterDescriptionResource] | None = Field(None, description="Available description resources")


class ParameterFlagSection(BaseResourceSection):
    current: list[ParameterFlagConfig] | None = Field(None, description="Currently active flag configs")
    resources: list[ParameterFlagConfig] | None = Field(None, description="Available flag configs")


class ParameterDepartmentSection(BaseResourceSection):
    current: list[ParameterDepartmentResource] | None = Field(None, description="Currently assigned departments")
    resources: list[ParameterDepartmentResource] | None = Field(None, description="Available departments")


class ParameterFieldSection(BaseResourceSection):
    current: list[ParameterFieldResource] | None = Field(None, description="Currently assigned fields")
    resources: list[ParameterFieldResource] | None = Field(None, description="Available fields")


# ---------------------------------------------------------------------------
# GET endpoint types
# ---------------------------------------------------------------------------


class GetParameterApiRequest(BaseModel):
    """Request model for get parameter endpoint."""

    parameter_id: UUID | None = Field(None, description="Parameter unique identifier")
    draft_id: UUID | None = Field(None, description="Draft unique identifier")


class GetParameterApiResponse(BaseModel):
    """Section-first client response for get parameter endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    parameter_exists: bool | None = Field(None, description="Whether the parameter exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Group identifier for the parameter")

    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    fields_step_show_ai_generate: bool | None = Field(None, description="Show AI generate for fields step")

    names: ParameterNameSection | None = Field(None, description="Name section with resources")
    descriptions: ParameterDescriptionSection | None = Field(None, description="Description section with resources")
    flags: ParameterFlagSection | None = Field(None, description="Flag section with configs")
    departments: ParameterDepartmentSection | None = Field(None, description="Department section with resources")
    fields: ParameterFieldSection | None = Field(None, description="Field section with resources")


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


class CreateParameterApiRequest(BaseModel):
    """Request model for bulk create parameter endpoint."""

    parameters: list[CreateParameterItem] = Field(..., description="List of parameters to create")


class CreateParameterApiResponse(BaseModel):
    """Response model for bulk create parameter endpoint."""

    results: list[ParameterResultItem] = Field(..., description="List of operation results")


# ========== Update Endpoint Types ==========


class UpdateParameterItem(BaseModel):
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


class UpdateParameterApiRequest(BaseModel):
    """Request model for bulk update parameter endpoint."""

    parameters: list[UpdateParameterItem] = Field(..., description="List of parameters to update")


class UpdateParameterApiResponse(BaseModel):
    """Response model for bulk update parameter endpoint."""

    results: list[ParameterResultItem] = Field(..., description="List of operation results")


class SaveParameterFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchParameterDraftApiRequest(BaseModel):
    """Request model for new-style parameter draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_ids, department_ids, field_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Existing draft ID to update")
    expected_version: int = Field(0, description="Expected draft version for concurrency")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="Name resource identifier")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="Description resource identifier")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Flag option identifiers")
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    field_ids: list[UUID] | None = Field(None, description="Field identifiers")


class ParameterDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource identifier")
    description_id: UUID | None = Field(None, description="Resolved description resource identifier")
    flag_ids: list[UUID] = Field(..., description="Flag option identifiers")
    department_ids: list[UUID] = Field(..., description="Department identifiers")
    field_ids: list[UUID] = Field(..., description="Field identifiers")


class PatchParameterDraftApiResponse(BaseModel):
    """Response model for new-style parameter draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="Draft unique identifier")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Result message")
    form_state: ParameterDraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Delete Endpoint Types ==========


class DeleteParameterApiRequest(BaseModel):
    """Request model for bulk delete parameter endpoint."""

    parameter_ids: list[UUID] = Field(..., description="List of parameter IDs to delete")


class DeleteParameterResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    parameter_id: UUID = Field(..., description="Deleted parameter identifier")
    message: str = Field(..., description="Result message")


class DeleteParameterApiResponse(BaseModel):
    """Response model for bulk delete parameter endpoint."""

    results: list[DeleteParameterResult] = Field(..., description="List of deletion results")


# ========== Duplicate Endpoint Types ==========


class DuplicateParameterApiRequest(BaseModel):
    parameter_id: UUID = Field(..., description="Parameter identifier to duplicate")


class DuplicateParameterApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    parameter_id: UUID = Field(..., description="New duplicated parameter identifier")
    message: str = Field(..., description="Result message")


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
