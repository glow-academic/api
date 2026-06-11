"""Handcrafted types for field artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.persona.types import ImportField
from app.infra.resource_type_filter import ScopedItem
from app.infra.shared_types import MAX_BULK_ITEMS, MAX_TEXT_FIELD_LEN
from app.tools.entries.field_drafts.types import GetFieldDraftResponse


class GetFieldDraftsApiRequest(BaseModel):
    """Request model for the field drafts list endpoint.

    Mirrors ``GenerationsFieldApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


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


class FieldFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'field_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
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
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    show_ai_generate: bool | None = Field(None, description="Whether to show AI generate button anywhere")
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate button")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[FieldNameResource] | None = Field(None, description="Name resources")
    descriptions: list[FieldDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[FieldFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    departments: list[FieldDepartmentResource] | None = Field(None, description="Department resources")
    conditional_parameters: list[FieldConditionalParameterResource] | None = Field(None, description="Conditional parameter resources")


# ========== List Endpoint Types ==========


class ListFieldApiField(BaseModel):
    id: UUID | None = Field(None, description="Field artifact UUID (canonical id; mirrors field_id)")
    field_id: UUID | None = Field(None, description="Unique field identifier")
    name: str | None = Field(None, description="Field display name")
    description: str | None = Field(None, description="Field description text")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Associated conditional parameter UUIDs")
    persona_ids: list[UUID] | None = Field(None, description="Associated persona UUIDs")
    is_inactive: bool | None = Field(None, description="Whether the field is inactive")
    # Soft-call ledger snapshot — set when this field has a pending op
    # in ``soft_calls_mv``. Client renders ghost/pending styling when set.
    pending_status: str | None = Field(None, description="Latest soft_calls_mv status: 'pending' / 'accepted' / 'rejected'")
    pending_operation: str | None = Field(None, description="Operation type ('create'|'update'|'delete'|'duplicate') of the pending op")
    pending_call_id: UUID | None = Field(None, description="call_id (idempotency key for ack) of the pending op")
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
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
    total_count: int | None = Field(None, description="Total number of fields")
    import_fields: list[ImportField] | None = Field(
        None, description="CSV import column schema for the bulk-import dialog"
    )


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
        "flag_ids": "flags",
        "active": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "conditional_parameter_ids": "conditional_parameters",
        "field_ids": "fields",
    }

    id: UUID | None = Field(None, description="Optional preset UUID for the new field")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Name value to resolve or create")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Description value to resolve or create")
    # Canonical multi-select flag ids + denormalized boolean for field_active.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized field_active flag state; resolved to a flag_ids entry server-side")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Conditional parameter UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Related field UUIDs")


class CreateFieldApiRequest(BaseModel):
    """Request model for bulk create field endpoint."""

    fields: list[CreateFieldItem] = Field(..., max_length=MAX_BULK_ITEMS, description="List of fields to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    soft: bool = Field(False, description="Stage the create dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateFieldApiResponse(BaseModel):
    """Response model for bulk create field endpoint."""

    results: list[FieldResultItem] = Field(..., description="Per-item creation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateFieldItem(ScopedItem):
    """Single field item for update — field_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateFieldItem.RESOURCE_TYPE_MAP

    id: UUID = Field(..., description="UUID of the field to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Name value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Description value to resolve or create")
    # Canonical multi-select flag ids + denormalized boolean for field_active.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized field_active flag state; resolved to a flag_ids entry server-side")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Conditional parameter UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Related field UUIDs")


class UpdateFieldPatch(UpdateFieldItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateFieldItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved field id per matched row",
    )


class UpdateFieldApiRequest(BaseModel):
    """Request model for bulk update field endpoint.

    Three body shapes:
      - First call (explicit): ``fields`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/field/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    fields: list[UpdateFieldItem] | None = Field(
        None, description="List of fields to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteFieldApiRequest; ``patch``
    # is the shared change set applied to every matched row. ``patch.id``
    # is ignored — each resolved id is stamped onto a clone before the
    # per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every field matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateFieldPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    parameter_ids: list[UUID] | None = Field(None, description="Filter by parameter UUIDs")
    persona_ids: list[UUID] | None = Field(None, description="Filter by persona UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    parameter_search: str | None = Field(None, description="Search text for parameter facet (no-op for row filtering)")
    persona_search: str | None = Field(None, description="Search text for persona facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    soft: bool = Field(False, description="Stage the update dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateFieldApiResponse(BaseModel):
    """Response model for bulk update field endpoint."""

    results: list[FieldResultItem] = Field(..., description="Per-item update results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


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
        "flag_ids": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "conditional_parameters": "conditional_parameters",
        "conditional_parameter_ids": "conditional_parameters",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to update")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Name value to resolve or create")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Description value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized field_active flag state; resolved to a flag_ids entry server-side")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Conditional parameter UUIDs")
    conditional_parameters: list[str] | None = Field(None, description="Conditional parameter names to resolve")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep pending where supported")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack or retry")
    soft: bool = Field(False, description="Stage the draft dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept or reject dormant state")


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    name: str | None = Field(None, description="Echoed name value")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    description: str | None = Field(None, description="Echoed description value")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed field_active flag state")
    department_ids: list[UUID] = Field(default_factory=list, description="Assigned department UUIDs")
    conditional_parameter_ids: list[UUID] = Field(default_factory=list, description="Assigned conditional parameter UUIDs")
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
    """Request model for bulk delete field endpoint.

    Three body shapes:
      - First call (explicit): ``field_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/field/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    field_ids: list[UUID] | None = Field(
        None, description="UUIDs of fields to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchFieldApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every field matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /field/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``field_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    parameter_ids: list[UUID] | None = Field(None, description="Filter by parameter UUIDs")
    persona_ids: list[UUID] | None = Field(None, description="Filter by persona UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    parameter_search: str | None = Field(None, description="Search text for parameter facet (no-op for row filtering)")
    persona_search: str | None = Field(None, description="Search text for persona facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    soft: bool = Field(False, description="Stage the delete dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (confirm deletion) or reject (restore). Only meaningful with idempotency_key")


class DeleteFieldResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    field_id: UUID | None = Field(None, description="UUID of the deleted field")
    message: str = Field(..., description="Result message")


class DeleteFieldApiResponse(BaseModel):
    """Response model for bulk delete field endpoint."""

    results: list[DeleteFieldResult] = Field(..., description="Per-item deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Duplicate Endpoint Types ==========


class DuplicateFieldApiRequest(BaseModel):
    field_id: UUID = Field(..., description="UUID of the field to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    soft: bool = Field(False, description="Stage the duplicate dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateFieldApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    field_id: UUID = Field(..., description="UUID of the newly created field")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Export Endpoint Types ==========


class ExportFieldApiRequest(BaseModel):
    """Request model for field export."""

    field_id: UUID | None = Field(None, description="UUID of the field to export")
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")
    soft: bool = Field(False, description="Stage the export dormant (active=False); ack with accept activates it")
    accept: bool | None = Field(None, description="Ack: True promotes the staged export, False rejects. Only meaningful with idempotency_key")


class ExportFieldApiResponse(BaseModel):
    """Response model for export field endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource holding the export CSV")
    file_name: str = Field(..., description="Suggested download file name")
    row_count: int = Field(..., description="Number of data rows in the export")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key (audit call_id). On a soft propose, echo this back with `accept` to promote/reject the staged export.")


class FileDownloadFieldApiRequest(BaseModel):
    """Request model for field file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadFieldApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


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
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


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
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemFieldApiResponse(BaseModel):
    """Response model for field problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadFieldApiRequest(BaseModel):
    """Request model for field text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadFieldApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadFieldApiRequest(BaseModel):
    """Request model for field call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadFieldApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
