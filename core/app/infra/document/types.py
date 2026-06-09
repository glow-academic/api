"""Handcrafted types for document endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field
from app.infra.shared_types import MAX_BULK_ITEMS

from app.infra.api_types import ListFilterSection
from app.infra.persona.types import ImportField
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.document_drafts.types import GetDocumentDraftResponse
from app.tools.resources.parameters.types import GetParameterResponse


class GetDocumentDraftsApiRequest(BaseModel):
    """Request model for the document drafts list endpoint.

    Mirrors ``GenerationsDocumentApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


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
    """File resource for document."""

    id: UUID | None = Field(None, description="Unique identifier")
    files_id: UUID | None = Field(None, description="File resource UUID")
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


class DocumentFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'document_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon")
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
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    show_ai_generate: bool | None = Field(None, description="Whether AI generation is available")
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for basic step")
    content_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for content step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource IDs from the draft, when available")

    names: list[DocumentNameResource] | None = Field(None, description="Name resources")
    descriptions: list[DocumentDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[DocumentFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
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

    id: UUID | None = Field(None, description="Document artifact UUID (canonical id; mirrors document_id)")
    document_id: UUID | None = Field(None, description="Document UUID")
    name: str | None = Field(None, description="Document name")
    description: str | None = Field(None, description="Document description")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Associated field UUIDs")
    flag_ids: list[UUID] | None = Field(None, description="Currently selected flag option UUIDs")
    is_inactive: bool | None = Field(None, description="Whether the document is inactive (derived from document_active flag)")
    is_template: bool | None = Field(None, description="Whether the document is a template (derived from document_template flag)")
    # Soft-call ledger snapshot — set when this document has a pending op
    # in ``soft_calls_mv``. Client renders ghost/pending styling when set.
    pending_status: str | None = Field(None, description="Latest soft_calls_mv status: 'pending' / 'accepted' / 'rejected'")
    pending_operation: str | None = Field(None, description="Operation type ('create'|'update'|'delete'|'duplicate') of the pending op")
    pending_call_id: UUID | None = Field(None, description="call_id (idempotency key for ack) of the pending op")
    extension: str | None = Field(None, description="File extension derived from the primary file (e.g. 'pdf', 'docx', 'txt')")
    num_scenarios: int | None = Field(None, description="Total number of scenarios")
    active_scenario_count: int | None = Field(None, description="Number of active scenarios")
    file_id: UUID | None = Field(None, description="Associated file resource UUID (binary/PDF content)")
    text_id: UUID | None = Field(None, description="Associated text resource UUID (HTML/plain-text content); the preview viewer prefers this when set")
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
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
    total_count: int | None = Field(None, description="Total number of matching records")
    import_fields: list[ImportField] | None = Field(
        None, description="CSV import column schema for the bulk-import dialog"
    )


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
        "flag_ids": "flags",
        "active": "flags",
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
    # Canonical multi-select flag ids + denormalized boolean for document_active.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized document_active flag state; resolved to a flag_ids entry server-side")
    # Multi-select — provide IDs or names
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    # Multi-select — IDs only
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs")
    upload_ids: list[UUID] | None = Field(None, description="File upload UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Image UUIDs")
    text_ids: list[UUID] | None = Field(None, description="Text resource UUIDs")
    # Direct resource references (set at creation, resolved later by file/text seed)
    file_id: UUID | None = Field(None, description="Files resource UUID for document file")
    text_id: UUID | None = Field(None, description="Texts resource UUID for document text")


class CreateDocumentApiRequest(BaseModel):
    """Request model for bulk create document endpoint."""

    documents: list[CreateDocumentItem] = Field(..., max_length=MAX_BULK_ITEMS, description="List of documents to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    soft: bool = Field(False, description="Stage the create dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


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

    id: UUID = Field(..., description="Document UUID to update")  # Required — which document to update
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Canonical multi-select flag ids + denormalized boolean for document_active.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized document_active flag state; resolved to a flag_ids entry server-side")
    # Multi-select — provide IDs or names
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    # Multi-select — IDs only
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs")
    upload_ids: list[UUID] | None = Field(None, description="File upload UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Image UUIDs")
    text_ids: list[UUID] | None = Field(None, description="Text resource UUIDs")


class UpdateDocumentPatch(UpdateDocumentItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateDocumentItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved document id per matched row",
    )


class UpdateDocumentApiRequest(BaseModel):
    """Request model for bulk update document endpoint.

    Three body shapes:
      - First call (explicit): ``documents`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/document/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    documents: list[UpdateDocumentItem] | None = Field(
        None, description="List of documents to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteDocumentApiRequest; ``patch``
    # is the shared change set applied to every matched row. ``patch.id``
    # is ignored — each resolved id is stamped onto a clone before the
    # per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every document matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateDocumentPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    scenario_ids: list[UUID] | None = Field(None, description="Filter by scenario UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Filter by field UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    scenario_search: str | None = Field(None, description="Search text for scenario facet (no-op for row filtering)")
    field_search: str | None = Field(None, description="Search text for field facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    soft: bool = Field(False, description="Stage the update dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


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
    """Request model for bulk delete document endpoint.

    Three body shapes:
      - First call (explicit): ``document_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/document/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    document_ids: list[UUID] | None = Field(
        None, description="Document UUIDs to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchDocumentApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every document matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /document/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``document_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    scenario_ids: list[UUID] | None = Field(None, description="Filter by scenario UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Filter by field UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    scenario_search: str | None = Field(None, description="Search text for scenario facet (no-op for row filtering)")
    field_search: str | None = Field(None, description="Search text for field facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    soft: bool = Field(False, description="Stage the delete dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (confirm deletion) or reject (restore). Only meaningful with idempotency_key")


class DeleteDocumentResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    document_id: UUID | None = Field(None, description="Document UUID")
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
    soft: bool = Field(False, description="Stage the duplicate dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


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
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized document_active flag state; resolved to a flag_ids entry server-side")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Image UUIDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs")
    parameter_ids: list[UUID] | None = Field(None, description="Parameter UUIDs")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep as pending where supported by the tool layer")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack or retry")
    soft: bool = Field(False, description="Stage the draft dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name: str | None = Field(None, description="Echoed unresolved name value")
    name_id: UUID | None = Field(None, description="Selected name resource UUID")
    description: str | None = Field(None, description="Echoed unresolved description value")
    description_id: UUID | None = Field(None, description="Selected description resource UUID")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed document_active flag state")
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
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")


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
    idempotency_key: UUID | None = Field(
        None,
        description="Server-minted soft-call key (the audit call_id). On a soft "
        "propose, echo this back with `accept` to promote/reject the staged upload.",
    )


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
    idempotency_key: UUID | None = Field(
        None,
        description="Server-minted soft-call key (the audit call_id). On a soft "
        "propose, echo this back with `accept` to promote/reject the staged upload.",
    )


class ImageUploadDocumentApiResponse(BaseModel):
    """Response model for document image upload endpoint. Mirrors scenario."""

    image_id: UUID = Field(..., description="UUID of the created images_resource")
    upload_id: UUID = Field(..., description="UUID of the underlying uploads_entry")
    idempotency_key: UUID | None = Field(
        None,
        description="Server-minted soft-call key (the audit call_id). On a soft "
        "propose, echo this back with `accept` to promote/reject the staged upload.",
    )


class ImageDownloadDocumentApiRequest(BaseModel):
    """Request model for document image download endpoint. Mirrors scenario."""

    image_id: UUID = Field(..., description="UUID of the images_resource to download")


class ImageDownloadDocumentApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


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
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


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
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemDocumentApiResponse(BaseModel):
    """Response model for document problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadDocumentApiRequest(BaseModel):
    """Request model for document call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadDocumentApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
