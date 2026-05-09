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


class ParameterFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) flags_resource entry."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
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
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    show_ai_generate: bool | None = Field(None, description="Show AI generate if any resource supports it")
    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    fields_step_show_ai_generate: bool | None = Field(None, description="Show AI generate for fields step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[ParameterNameResource] | None = Field(None, description="Name resources")
    descriptions: list[ParameterDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[ParameterFlagResource] | None = Field(None, description="Flag configs")
    departments: list[ParameterDepartmentResource] | None = Field(None, description="Department resources")
    parameter_fields: list[ParameterFieldResource] | None = Field(None, description="Parameter field resources")


class GetParameterDraftsApiRequest(BaseModel):
    """Request model for the parameter drafts list endpoint.

    Mirrors ``GenerationsParameterApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GetParameterDraftsApiResponse(BaseModel):
    """Response model for parameter drafts list endpoint."""

    entries: list[GetParameterDraftResponse] | None = Field(None, description="List of parameter draft entries")


# ========== List Endpoint Types ==========


class ListParameterApiParameter(BaseModel):
    parameter_id: UUID | None = Field(None, description="Parameter unique identifier")
    name: str | None = Field(None, description="Display name of the parameter")
    description: str | None = Field(None, description="Parameter description text")
    active: bool | None = Field(None, description="Whether this parameter is currently active")
    is_inactive: bool | None = Field(None, description="Whether the parameter is inactive")
    department_ids: list[str] | None = Field(None, description="Associated department identifiers")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario identifiers")
    document_ids: list[UUID] | None = Field(None, description="Associated document identifiers")
    num_items: int | None = Field(None, description="Number of items in this parameter")
    sample_items: list[str] | None = Field(None, description="Sample items for preview")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    updated_at: datetime | None = Field(None, description="Timestamp of last update")
    pending_status: str | None = Field(None, description="Pending soft_calls_entry status (e.g. 'pending')")
    pending_operation: str | None = Field(None, description="Pending operation (create/update/delete/duplicate)")
    pending_call_id: UUID | None = Field(None, description="Originating tool call id for ack")


class ListParameterApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    parameters: list[ListParameterApiParameter] | None = Field(None, description="List of parameter entries")
    scenario_filter: ListFilterSection | None = Field(None, description="Scenario filter options")
    field_filter: ListFilterSection | None = Field(None, description="Field filter options")
    department_filter: ListFilterSection | None = Field(None, description="Department filter options")
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
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
    """Single parameter item for create — no parameter_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Optional pre-assigned identifier")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of an existing name resource")
    name: str | None = Field(None, description="REQUIRED FOR CREATE (or pass `name_id`) — display name text (creates new resource if name_id not provided)")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of an existing description resource")
    description: str | None = Field(None, description="Description text value (creates new resource if description_id not provided)")
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
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateParameterApiResponse(BaseModel):
    """Response model for bulk create parameter endpoint."""

    results: list[ParameterResultItem] = Field(..., description="List of operation results")
    parameters: list[ListParameterApiParameter] | None = Field(
        None,
        description=(
            "Hydrated list rows for the just-created parameters — same shape as "
            "``/parameter/search`` returns. Lets the client materialize the new "
            "rows directly from the response (or audit ``.completed`` payload) "
            "without a follow-up search burst. Omitted on the soft-pending "
            "(ack-shaped) paths — dormant rows aren't fully active until accepted."
        ),
    )
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateParameterItem(ScopedItem):
    """Single parameter item for update — parameter_id required, all fields optional."""

    id: UUID = Field(..., description="Target parameter identifier to update")
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


class UpdateParameterPatch(UpdateParameterItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateParameterItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved parameter id per matched row",
    )


class UpdateParameterApiRequest(BaseModel):
    """Request model for bulk update parameter endpoint.

    Three body shapes:
      - First call (explicit): ``parameters`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/parameter/search`` accepts plus a single shared ``patch``
        that every matched row receives. The impl resolves matching
        ids, subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    parameters: list[UpdateParameterItem] | None = Field(
        None, description="List of parameters to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteParameterApiRequest;
    # ``patch`` is the shared change set applied to every matched row.
    # ``patch.id`` is ignored — each resolved id is stamped onto a clone
    # before the per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every parameter matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateParameterPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
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
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateParameterApiResponse(BaseModel):
    """Response model for bulk update parameter endpoint."""

    results: list[ParameterResultItem] = Field(..., description="List of operation results")
    parameters: list[ListParameterApiParameter] | None = Field(
        None,
        description=(
            "Hydrated list rows for the just-updated parameters — same shape as "
            "``/parameter/search`` returns. Lets the client patch in updated "
            "rows directly from the response without a follow-up search. Omitted "
            "on the soft-pending (ack-shaped) paths."
        ),
    )
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
    accept: bool | None = Field(None, description="Accept or reject dormant state")

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
    """Request model for bulk delete parameter endpoint.

    Three body shapes:
      - First call (explicit): ``parameter_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/parameter/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    parameter_ids: list[UUID] | None = Field(
        None, description="UUIDs of parameters to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchParameterApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every parameter matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /parameter/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``parameter_ids`` is set.
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
    accept: bool | None = Field(None, description="Accept (confirm deletion) or reject (restore). Only meaningful with idempotency_key")


class DeleteParameterResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    # ``UUID | None`` so soft-skipped not-found rows can be reported
    # under the all-matching path (where the input id didn't resolve
    # to an actual artifact). Explicit-ids path still raises 404 for
    # missing rows; this stays None only for diagnostic results.
    parameter_id: UUID | None = Field(None, description="Deleted parameter identifier (None for soft-skipped not-found rows)")
    message: str = Field(..., description="Result message")


class DeleteParameterApiResponse(BaseModel):
    """Response model for bulk delete parameter endpoint."""

    results: list[DeleteParameterResult] = Field(..., description="List of deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Duplicate Endpoint Types ==========


class DuplicateParameterApiRequest(BaseModel):
    parameter_id: UUID = Field(..., description="Parameter identifier to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateParameterApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    parameter_id: UUID = Field(..., description="New duplicated parameter identifier")
    message: str = Field(..., description="Result message")
    parameters: list[ListParameterApiParameter] | None = Field(
        None,
        description=(
            "Hydrated list row for the just-duplicated parameter — single-element "
            "list for shape consistency with create / update. Same shape as "
            "``/parameter/search`` returns. Omitted on the soft-pending "
            "(ack-shaped) path."
        ),
    )
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
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemParameterApiResponse(BaseModel):
    """Response model for parameter problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadParameterApiRequest(BaseModel):
    """Request model for parameter text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadParameterApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadParameterApiRequest(BaseModel):
    """Request model for parameter call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadParameterApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
