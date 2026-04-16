"""Handcrafted types for document endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.resource_type_filter import ScopedItem
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
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DocumentDescriptionResource(BaseModel):
    """Description resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DocumentDepartmentResource(BaseModel):
    """Department resource for document."""

    department_id: UUID | None = Field(None, description="Department UUID")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DocumentParameterFieldResource(BaseModel):
    """Parameter field resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    field_id: UUID | None = Field(None, description="Associated field UUID")
    parameter_id: UUID | None = Field(None, description="Associated parameter UUID")
    name: str | None = Field(None, description="Field name")
    description: str | None = Field(None, description="Field description")
    conditional_parameter_id: str | None = Field(None, description="Conditional parameter UUID for grouping")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DocumentParameterResource(BaseModel):
    """Parameter catalog item exposed to the client."""

    parameter_id: UUID | None = Field(None, description="Parameter UUID")
    name: str | None = Field(None, description="Parameter name")
    description: str | None = Field(None, description="Parameter description")
    value: str | None = Field(None, description="Parameter value")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    persona_parameter: bool | None = Field(None, description="Whether this is a persona parameter")
    document_parameter: bool | None = Field(None, description="Whether this is a document parameter")
    scenario_parameter: bool | None = Field(None, description="Whether this is a scenario parameter")
    video_parameter: bool | None = Field(None, description="Whether this is a video parameter")
    field_ids: list[UUID] | None = Field(None, description="Associated field UUIDs")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DocumentFileResource(BaseModel):
    """File (upload) resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    files_id: UUID | None = Field(None, description="File resource UUID")
    upload_id: UUID | None = Field(None, description="Upload UUID")
    file_path: str | None = Field(None, description="Stored file path")
    mime_type: str | None = Field(None, description="File MIME type")
    size: int | None = Field(None, description="File size in bytes")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DocumentImageResource(BaseModel):
    """Image resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    image_id: UUID | None = Field(None, description="Image resource UUID")
    name: str | None = Field(None, description="Image name")
    description: str | None = Field(None, description="Image description")
    upload_id: UUID | None = Field(None, description="Upload UUID")
    file_path: str | None = Field(None, description="Stored file path")
    mime_type: str | None = Field(None, description="File MIME type")
    size: int | None = Field(None, description="File size in bytes")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DocumentTextResource(BaseModel):
    """Text resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    texts_id: UUID | None = Field(None, description="Text resource UUID")
    upload_id: UUID | None = Field(None, description="Upload UUID")
    file_path: str | None = Field(None, description="Stored file path")
    mime_type: str | None = Field(None, description="File MIME type")
    content: str | None = Field(None, description="Optional text content when available")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class DocumentDraftEntry(BaseModel):
    """Draft entry for document."""

    id: UUID | None = Field(None, description="Unique identifier")

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
    parameter_ids: list[str] | None = Field(None, description="Parameter group IDs for parameter field hydration")


class GetDocumentApiRequest(BaseModel):
    """Request model for get document endpoint."""

    id: UUID | None = Field(None, description="Document UUID to retrieve")
    document_id: UUID | None = Field(None, description="Legacy alias for the document UUID")
    draft_id: UUID | None = Field(None, description="Draft UUID to load from")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    parameter_fields: SectionFilter | None = Field(None, description="Filter options for parameter fields section")
    parameters: SectionFilter | None = Field(None, description="Filter options for parameters section")
    files: SectionFilter | None = Field(None, description="Filter options for files section")
    images: SectionFilter | None = Field(None, description="Filter options for images section")
    texts: SectionFilter | None = Field(None, description="Filter options for texts section")
    fields: SectionFilter | None = Field(None, description="Legacy alias for parameter_fields")
    uploads: SectionFilter | None = Field(None, description="Legacy alias for files")


class GetDocumentApiResponse(BaseModel):
    """Canonical flat composed response for the document editor."""

    actor_name: str | None = Field(None, description="Display name of the current user")
    document_exists: bool | None = Field(None, description="Whether the document exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    group_id: UUID | None = Field(None, description="Associated group UUID")
    show_ai_generate: bool | None = Field(None, description="Whether AI generation is available")
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for basic step")
    content_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for content step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource IDs from the draft, when available")

    names: list[DocumentNameResource] | None = Field(None, description="Name resources")
    descriptions: list[DocumentDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[DocumentFlagConfig] | None = Field(None, description="Flag configs")
    departments: list[DocumentDepartmentResource] | None = Field(None, description="Department resources")
    parameter_fields: list[DocumentParameterFieldResource] | None = Field(None, description="Parameter field resources")
    parameters: list[DocumentParameterResource] | None = Field(None, description="Parameter catalog resources")
    files: list[DocumentFileResource] | None = Field(None, description="File resources")
    images: list[DocumentImageResource] | None = Field(None, description="Image resources")
    texts: list[DocumentTextResource] | None = Field(None, description="Text resources")


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


class CreateDocumentItem(ScopedItem):
    """Single document item for create — no document_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "flag_id": "flags",
        "active_flag_id": "flags",
        "active_flag": "flags",
        "template_flag": "flags",
        "template_flag_id": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "parameter_field_ids": "parameter_fields",
        "upload_ids": "uploads",
        "image_ids": "images",
        "text_ids": "texts",
    }

    id: UUID | None = Field(None, description="Optional pre-assigned UUID")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Flag — provide ID or boolean
    flag_id: UUID | None = Field(None, description="Flag option UUID")
    active_flag_id: UUID | None = Field(None, description="UUID of the flag option to set active status")
    active_flag: bool | None = Field(None, description="Whether the document is active (resolved to flag_id)")
    template_flag: bool | None = Field(None, description="Whether this is a template document")
    template_flag_id: UUID | None = Field(None, description="Template flag resource UUID")
    # Multi-select — provide IDs or names
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    # Multi-select — IDs only
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs")
    upload_ids: list[UUID] | None = Field(None, description="File upload UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Image UUIDs")
    text_ids: list[UUID] | None = Field(None, description="Text resource UUIDs")


class CreateDocumentApiRequest(BaseModel):
    """Request model for bulk create document endpoint."""

    documents: list[CreateDocumentItem] = Field(..., description="List of documents to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateDocumentApiResponse(BaseModel):
    """Response model for bulk create document endpoint."""

    results: list[DocumentResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateDocumentItem(ScopedItem):
    """Single document item for update — document_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateDocumentItem.RESOURCE_TYPE_MAP

    document_id: UUID = Field(..., description="Document UUID to update")  # Required — which document to update
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Flag — provide ID or boolean
    flag_id: UUID | None = Field(None, description="Flag option UUID")
    active_flag_id: UUID | None = Field(None, description="UUID of the flag option to set active status")
    active_flag: bool | None = Field(None, description="Whether the document is active (resolved to flag_id)")
    template_flag: bool | None = Field(None, description="Whether this is a template document")
    template_flag_id: UUID | None = Field(None, description="Template flag resource UUID")
    # Multi-select — provide IDs or names
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    # Multi-select — IDs only
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs")
    upload_ids: list[UUID] | None = Field(None, description="File upload UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Image UUIDs")
    text_ids: list[UUID] | None = Field(None, description="Text resource UUIDs")


class UpdateDocumentApiRequest(BaseModel):
    """Request model for bulk update document endpoint."""

    documents: list[UpdateDocumentItem] = Field(..., description="List of documents to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateDocumentApiResponse(BaseModel):
    """Response model for bulk update document endpoint."""

    results: list[DocumentResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveDocumentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


# ========== Delete Endpoint Types ==========


class DeleteDocumentApiRequest(BaseModel):
    """Request model for bulk delete document endpoint."""

    document_ids: list[UUID] = Field(..., description="Document UUIDs to delete")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm deletion) or reject (restore). Only meaningful with idempotency_key")


class DeleteDocumentResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    document_id: UUID = Field(..., description="Document UUID")
    message: str = Field(..., description="Human-readable result message")


class DeleteDocumentApiResponse(BaseModel):
    """Response model for bulk delete document endpoint."""

    results: list[DeleteDocumentResult] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Duplicate Endpoint Types ==========


class DuplicateDocumentApiRequest(BaseModel):
    """Request model for duplicate document endpoint."""

    document_id: UUID = Field(..., description="Document UUID to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateDocumentApiResponse(BaseModel):
    """Response model for duplicate document endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    document_id: UUID = Field(..., description="Newly created document UUID")
    message: str = Field(..., description="Human-readable result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


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


class DraftImageValue(BaseModel):
    """Value for creating an image via the draft endpoint."""

    name: str = Field(..., description="Image name")
    description: str = Field(..., description="Image description text")
    upload_id: UUID | None = Field(None, description="Associated upload UUID")


class PatchDocumentDraftApiRequest(ScopedItem):
    """Request model for the canonical document draft endpoint."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "files": "files",
        "file_ids": "files",
        "texts": "texts",
        "text_ids": "texts",
        "images": "images",
        "flag_ids": "flags",
        "department_ids": "departments",
        "image_ids": "images",
        "parameter_field_ids": "parameter_fields",
        "parameter_ids": "parameters",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to patch")
    input_draft_id: UUID | None = Field(None, description="Legacy alias for existing draft UUID to patch")

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
    images: list[DraftImageValue] | None = Field(None, description="Image values to create resources")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Flag option UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Image UUIDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs")
    parameter_ids: list[UUID] | None = Field(None, description="Parameter UUIDs")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep as pending where supported by the tool layer")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack or retry")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name: str | None = Field(None, description="Echoed unresolved name value")
    name_id: UUID | None = Field(None, description="Selected name resource UUID")
    description: str | None = Field(None, description="Echoed unresolved description value")
    description_id: UUID | None = Field(None, description="Selected description resource UUID")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    department_ids: list[UUID] = Field(default_factory=list, description="Selected department UUIDs")
    file_ids: list[UUID] = Field(default_factory=list, description="Selected file resource UUIDs")
    image_ids: list[UUID] = Field(default_factory=list, description="Selected image UUIDs")
    text_ids: list[UUID] = Field(default_factory=list, description="Selected text resource UUIDs")
    parameter_field_ids: list[UUID] = Field(default_factory=list, description="Selected parameter field UUIDs")
    parameter_ids: list[UUID] = Field(default_factory=list, description="Selected parameter UUIDs")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource UUIDs where supported")


DocumentDraftFormState = DraftFormState


class PatchDocumentDraftApiResponse(BaseModel):
    """Response model for new-style document draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="Draft UUID")
    idempotency_key: UUID = Field(..., description="Idempotency key for this draft operation")
    message: str = Field(..., description="Human-readable result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


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


# =============================================================================
# Text Upload/Download Types
# =============================================================================


class TextUploadDocumentApiResponse(BaseModel):
    """Response model for document text upload endpoint."""

    text_id: UUID = Field(..., description="UUID of the created texts_resource")
    upload_id: UUID = Field(..., description="UUID of the uploads_entry (file on disk)")


class TextDownloadDocumentApiRequest(BaseModel):
    """Request model for document text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadDocumentApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# File Upload/Download/Preview Types
# =============================================================================


class FileUploadDocumentApiResponse(BaseModel):
    """Response model for document file upload endpoint."""

    file_id: UUID = Field(..., description="UUID of the created files_resource")
    upload_id: UUID = Field(..., description="UUID of the uploads_entry (file on disk)")


class FileDownloadDocumentApiRequest(BaseModel):
    """Request model for document file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadDocumentApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


class FilePreviewDocumentApiRequest(BaseModel):
    """Request model for document file preview endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to preview")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsDocumentApiRequest(BaseModel):
    """Request model for document generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsDocumentListItem(BaseModel):
    """Single generation group in the document generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsDocumentApiResponse(BaseModel):
    """Response model for document generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsDocumentListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemDocumentApiRequest(BaseModel):
    """Request model for document problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemDocumentApiResponse(BaseModel):
    """Response model for document problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
