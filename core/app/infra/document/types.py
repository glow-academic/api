"""Handcrafted types for document endpoints.

Section-first API responses following the gold standard pattern (REFERENCE.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.document.create import CreateDocumentItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.document_drafts.types import GetDocumentDraftResponse
from app.tools.resources.parameters.types import GetParameterResponse


class GetDocumentDraftsApiResponse(BaseModel):
    """Response model for document drafts list endpoint."""

    entries: list[GetDocumentDraftResponse] | None = Field(None, description="List of document draft entries")


# ---------------------------------------------------------------------------
# Handcrafted resource types (replaces Q types from app.sql.types)
# ---------------------------------------------------------------------------


class DocumentNameResource(BaseModel):
    """Name resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class DocumentDescriptionResource(BaseModel):
    """Description resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class DocumentDepartmentResource(BaseModel):
    """Department resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class DocumentParameterFieldResource(BaseModel):
    """Parameter field resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    field_id: UUID | None = Field(None, description="Associated field UUID")
    parameter_id: UUID | None = Field(None, description="Associated parameter UUID")
    name: str | None = Field(None, description="Field name")
    description: str | None = Field(None, description="Field description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class DocumentFileResource(BaseModel):
    """File (upload) resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class DocumentImageResource(BaseModel):
    """Image resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class DocumentTextResource(BaseModel):
    """Text resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class DocumentDraftEntry(BaseModel):
    """Draft entry for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    version: int | None = Field(None, description="Draft version number")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")
    active: bool | None = Field(None, description="Whether this draft is active")
    group_id: UUID | None = Field(None, description="Associated group UUID")
    session_id: UUID | None = Field(None, description="Associated session UUID")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    description_ids: list[UUID] | None = Field(None, description="Description resource UUIDs")
    file_ids: list[UUID] | None = Field(None, description="File resource UUIDs")
    flag_ids: list[UUID] | None = Field(None, description="Flag option UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Image resource UUIDs")
    name_ids: list[UUID] | None = Field(None, description="Name resource UUIDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs")
    parameter_ids: list[UUID] | None = Field(None, description="Parameter UUIDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs")
    text_ids: list[UUID] | None = Field(None, description="Text resource UUIDs")


# ========== GET Endpoint Types ==========


class DocumentFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")  # e.g., "active"
    label: str = Field(..., description="Display label")  # e.g., "Active"
    description: str | None = Field(None, description="Flag description")
    flag_option_id: UUID | None = Field(None, description="Flag option UUID to use when enabling")  # ID to use when enabling
    show: bool = Field(True, description="Whether to show this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class GetDocumentApiRequest(BaseModel):
    """Request model for get document endpoint."""

    document_id: UUID | None = Field(None, description="Document UUID to retrieve")
    draft_id: UUID | None = Field(None, description="Draft UUID to load from")


class DocumentNameSection(BaseResourceSection):
    resource: DocumentNameResource | None = Field(None, description="Currently selected name resource")
    resources: list[DocumentNameResource] | None = Field(None, description="Available name resources")


class DocumentDescriptionSection(BaseResourceSection):
    resource: DocumentDescriptionResource | None = Field(None, description="Currently selected description resource")
    resources: list[DocumentDescriptionResource] | None = Field(None, description="Available description resources")


class DocumentFlagSection(BaseResourceSection):
    current: list[DocumentFlagConfig] | None = Field(None, description="Currently selected flag configs")
    resources: list[DocumentFlagConfig] | None = Field(None, description="Available flag configs")


class DocumentDepartmentSection(BaseResourceSection):
    current: list[DocumentDepartmentResource] | None = Field(None, description="Currently selected departments")
    resources: list[DocumentDepartmentResource] | None = Field(None, description="Available departments")


class DocumentFieldSection(BaseResourceSection):
    current: list[DocumentParameterFieldResource] | None = Field(None, description="Currently selected parameter fields")
    resources: list[DocumentParameterFieldResource] | None = Field(None, description="Available parameter fields")


class DocumentParameterSection(BaseResourceSection):
    current: list[GetParameterResponse] | None = Field(None, description="Currently selected parameters")
    resources: list[GetParameterResponse] | None = Field(None, description="Available parameters")


class DocumentUploadSection(BaseResourceSection):
    current: list[DocumentFileResource] | None = Field(None, description="Currently selected file uploads")
    resources: list[DocumentFileResource] | None = Field(None, description="Available file uploads")


class DocumentImageSection(BaseResourceSection):
    current: list[DocumentImageResource] | None = Field(None, description="Currently selected images")
    resources: list[DocumentImageResource] | None = Field(None, description="Available images")


class DocumentTextSection(BaseResourceSection):
    current: list[DocumentTextResource] | None = Field(None, description="Currently selected text resources")
    resources: list[DocumentTextResource] | None = Field(None, description="Available text resources")


class GetDocumentApiResponse(BaseModel):
    """Section-first response for document editor."""

    actor_name: str | None = Field(None, description="Display name of the current user")
    document_exists: bool | None = Field(None, description="Whether the document exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Associated group UUID")

    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for basic step")
    content_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for content step")

    names: DocumentNameSection | None = Field(None, description="Name section with resource and options")
    descriptions: DocumentDescriptionSection | None = Field(None, description="Description section with resource and options")
    flags: DocumentFlagSection | None = Field(None, description="Flag section with selections and options")
    departments: DocumentDepartmentSection | None = Field(None, description="Department section with selections and options")
    fields: DocumentFieldSection | None = Field(None, description="Parameter field section")
    parameters: DocumentParameterSection | None = Field(None, description="Parameter section with selections and options")
    uploads: DocumentUploadSection | None = Field(None, description="Upload section with selections and options")
    images: DocumentImageSection | None = Field(None, description="Image section with selections and options")
    texts: DocumentTextSection | None = Field(None, description="Text section with selections and options")


# ========== Internal Helper Types (used by get.py intermediate layer) ==========


class DocumentResourceBucket(BaseModel):
    """Internal bucket for holding resource lists during get_document_internal processing."""

    names: list[Any] | None = Field(None, description="List of name resources")
    descriptions: list[Any] | None = Field(None, description="List of description resources")
    flags: list[Any] | None = Field(None, description="List of flag config resources")
    departments: list[Any] | None = Field(None, description="List of department resources")
    fields: list[Any] | None = Field(None, description="List of parameter field resources")
    uploads: list[Any] | None = Field(None, description="List of file upload resources")
    images: list[Any] | None = Field(None, description="List of image resources")
    texts: list[Any] | None = Field(None, description="List of text resources")


class DocumentResources(BaseModel):
    """Internal resources container with 'resources' (all) and 'current' (selected) buckets."""

    resources: DocumentResourceBucket | None = Field(None, description="All available resources")
    current: DocumentResourceBucket | None = Field(None, description="Currently selected resources")


# ========== List Endpoint Types ==========


class ListDocumentApiDocument(BaseModel):
    """Document type for list endpoint with computed permissions."""

    document_id: UUID | None = Field(None, description="Document UUID")
    name: str | None = Field(None, description="Document name")
    description: str | None = Field(None, description="Document description")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Associated field UUIDs")
    is_inactive: bool | None = Field(None, description="Whether the document is inactive")
    num_scenarios: int | None = Field(None, description="Total number of scenarios")
    active_scenario_count: int | None = Field(None, description="Number of active scenarios")
    upload_id: UUID | None = Field(None, description="Associated upload UUID")
    # Computed in Python
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")


class ListDocumentApiResponse(BaseModel):
    """Response model for list document endpoint with computed permissions."""

    actor_name: str | None = Field(None, description="Display name of the current user")
    documents: list[ListDocumentApiDocument] | None = Field(None, description="List of documents")
    scenario_filter: ListFilterSection | None = Field(None, description="Filter options for scenarios in list UI")
    field_filter: ListFilterSection | None = Field(None, description="Filter options for fields in list UI")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments in list UI")
    total_count: int | None = Field(None, description="Total number of matching records")


# ========== Shared Create/Update Types ==========


class DocumentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


class DocumentResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    document_id: UUID | None = Field(None, description="Document UUID")
    message: str = Field(..., description="Human-readable result message")
    errors: list[DocumentFieldError] | None = Field(None, description="List of per-field errors")


# ========== Create Endpoint Types ==========


class CreateDocumentApiRequest(BaseModel):
    """Request model for bulk create document endpoint."""

    documents: list[CreateDocumentItem] = Field(..., description="List of documents to create")


class CreateDocumentApiResponse(BaseModel):
    """Response model for bulk create document endpoint."""

    results: list[DocumentResultItem] = Field(..., description="List of operation results")


# ========== Update Endpoint Types ==========


class UpdateDocumentItem(BaseModel):
    """Single document item for update — document_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    document_id: UUID = Field(..., description="Document UUID to update")  # Required — which document to update
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Flag — provide ID or boolean
    flag_id: UUID | None = Field(None, description="Flag option UUID")
    is_inactive: bool | None = Field(None, description="Whether the document is inactive")
    # Multi-select — provide IDs or names
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    # Multi-select — IDs only
    field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs")
    upload_ids: list[UUID] | None = Field(None, description="File upload UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Image UUIDs")
    text_ids: list[UUID] | None = Field(None, description="Text resource UUIDs")


class UpdateDocumentApiRequest(BaseModel):
    """Request model for bulk update document endpoint."""

    documents: list[UpdateDocumentItem] = Field(..., description="List of documents to update")


class UpdateDocumentApiResponse(BaseModel):
    """Response model for bulk update document endpoint."""

    results: list[DocumentResultItem] = Field(..., description="List of operation results")


class SaveDocumentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


# ========== Delete Endpoint Types ==========


class DeleteDocumentApiRequest(BaseModel):
    """Request model for bulk delete document endpoint."""

    document_ids: list[UUID] = Field(..., description="Document UUIDs to delete")


class DeleteDocumentResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    document_id: UUID = Field(..., description="Document UUID")
    message: str = Field(..., description="Human-readable result message")


class DeleteDocumentApiResponse(BaseModel):
    """Response model for bulk delete document endpoint."""

    results: list[DeleteDocumentResult] = Field(..., description="List of operation results")


# ========== Duplicate Endpoint Types ==========


class DuplicateDocumentApiRequest(BaseModel):
    """Request model for duplicate document endpoint."""

    document_id: UUID = Field(..., description="Document UUID to duplicate")


class DuplicateDocumentApiResponse(BaseModel):
    """Response model for duplicate document endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    document_id: UUID = Field(..., description="Newly created document UUID")
    message: str = Field(..., description="Human-readable result message")


# ========== Draft Endpoint Types ==========


class DraftFileValue(BaseModel):
    """Value for creating a file via the draft endpoint.

    Client provides the upload_id from a finalized TUS upload.
    Server creates the full chain: files_resource → files_entry → file_uploads_entry.
    """

    upload_id: UUID = Field(..., description="Upload UUID from a finalized TUS upload")


class DraftTextValue(BaseModel):
    """Value for creating a text via the draft endpoint.

    Client provides text content.
    Server creates the full chain: uploads_entry → texts_resource → texts_entry → text_uploads_entry.
    """

    content: str = Field(..., description="Text content to create")


class PatchDocumentDraftApiRequest(BaseModel):
    """Request model for new-style document draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
      - files (upload_id) / file_ids
      - texts (content) / text_ids
    ID-only for non-creatable resources:
      - flag_ids, department_ids, image_ids, parameter_field_ids, parameter_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to patch")
    expected_version: int = Field(0, description="Expected draft version for concurrency control")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to create a resource")
    name_id: UUID | None = Field(None, description="Existing name resource UUID")
    description: str | None = Field(None, description="Description value to create a resource")
    description_id: UUID | None = Field(None, description="Existing description resource UUID")

    # Creatable multi-select (merged mode) — values create resources, IDs merged
    files: list[DraftFileValue] | None = Field(None, description="File values to create resources")
    file_ids: list[UUID] | None = Field(None, description="Existing file resource UUIDs")
    texts: list[DraftTextValue] | None = Field(None, description="Text values to create resources")
    text_ids: list[UUID] | None = Field(None, description="Existing text resource UUIDs")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Flag option UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Image UUIDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs")
    parameter_ids: list[UUID] | None = Field(None, description="Parameter UUIDs")


class DocumentDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Selected name resource UUID")
    description_id: UUID | None = Field(None, description="Selected description resource UUID")
    flag_ids: list[UUID] = Field(..., description="Selected flag option UUIDs")
    department_ids: list[UUID] = Field(..., description="Selected department UUIDs")
    file_ids: list[UUID] = Field(..., description="Selected file resource UUIDs")
    image_ids: list[UUID] = Field(..., description="Selected image UUIDs")
    text_ids: list[UUID] = Field(..., description="Selected text resource UUIDs")
    parameter_field_ids: list[UUID] = Field(..., description="Selected parameter field UUIDs")
    parameter_ids: list[UUID] = Field(..., description="Selected parameter UUIDs")


class PatchDocumentDraftApiResponse(BaseModel):
    """Response model for new-style document draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="Draft UUID")
    new_version: int = Field(..., description="New draft version number after patch")
    message: str = Field(..., description="Human-readable result message")
    form_state: DocumentDraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Export Endpoint Types ==========


class ExportDocumentApiRequest(BaseModel):
    """Request model for document export."""

    document_id: UUID | None = Field(None, description="Document UUID to export")


class ExportDocumentApiResponse(BaseModel):
    """Response model for export document endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")
