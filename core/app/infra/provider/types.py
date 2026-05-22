"""Handcrafted types for provider artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.persona.types import ImportField
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.provider_drafts.types import GetProviderDraftResponse


class ProviderNameResource(BaseModel):
    id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Provider display name")
    generated: bool | None = Field(None, description="Whether the name was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ProviderDescriptionResource(BaseModel):
    id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Provider description")
    generated: bool | None = Field(None, description="Whether the description was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ProviderDepartmentResource(BaseModel):
    department_id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether the department was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ProviderValueResource(BaseModel):
    id: UUID | None = Field(None, description="Value resource identifier")
    value: str | None = Field(None, description="Provider value")
    value_type: str | None = Field(None, description="Stored value type")
    generated: bool | None = Field(None, description="Whether the value was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ProviderEndpointResource(BaseModel):
    id: UUID | None = Field(None, description="Endpoint resource identifier")
    base_url: str | None = Field(None, description="Endpoint base URL")
    generated: bool | None = Field(None, description="Whether the endpoint was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ProviderKeyResource(BaseModel):
    id: UUID | None = Field(None, description="Key resource identifier")
    key: str | None = Field(None, description="Provider key value")
    name: str | None = Field(None, description="Key display name")
    description: str | None = Field(None, description="Key description")
    generated: bool | None = Field(None, description="Whether the key was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ProviderFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'provider_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether this flag was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SectionFilter(BaseModel):
    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")


class GetProviderApiRequest(BaseModel):
    """Request model for get provider endpoint."""

    id: UUID | None = Field(None, description="Provider unique identifier")
    provider_id: UUID | None = Field(None, description="Legacy alias for provider unique identifier")
    draft_id: UUID | None = Field(None, description="Draft unique identifier")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions")
    flags: SectionFilter | None = Field(None, description="Filter options for flags")
    departments: SectionFilter | None = Field(None, description="Filter options for departments")
    values: SectionFilter | None = Field(None, description="Filter options for values")
    endpoints: SectionFilter | None = Field(None, description="Filter options for endpoints")
    keys: SectionFilter | None = Field(None, description="Filter options for keys")


class GetProviderApiResponse(BaseModel):
    """Canonical composed response for provider editor."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    provider_exists: bool | None = Field(None, description="Whether the provider exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    group_id: UUID | None = Field(None, description="Group identifier for the provider")
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    provider_id: UUID | None = Field(None, description="Provider identifier")
    show_ai_generate: bool | None = Field(None, description="Whether any step should show AI generate")

    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    integrations_show_ai_generate: bool | None = Field(None, description="Show AI generate for integrations step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")

    names: list[ProviderNameResource] | None = Field(None, description="Name resources")
    descriptions: list[ProviderDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[ProviderFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    departments: list[ProviderDepartmentResource] | None = Field(None, description="Department resources")
    values: list[ProviderValueResource] | None = Field(None, description="Value resources")
    endpoints: list[ProviderEndpointResource] | None = Field(None, description="Endpoint resources")
    keys: list[ProviderKeyResource] | None = Field(None, description="Key resources")


class ListProviderApiProvider(BaseModel):
    """Provider type for list endpoint with computed permissions."""

    provider_id: UUID | None = Field(None, description="Provider unique identifier")
    name: str | None = Field(None, description="Display name of the provider")
    description: str | None = Field(None, description="Provider description text")
    value: str | None = Field(None, description="Internal value or model identifier")
    active: bool | None = Field(None, description="Whether this provider is currently active")
    is_inactive: bool | None = Field(None, description="Whether the provider is inactive")
    updated_at: datetime | None = Field(None, description="Timestamp of last update")
    department_ids: list[UUID] | None = Field(None, description="Associated department identifiers")
    model_usage_count: int | None = Field(None, description="Number of models using this provider")
    model_ids: list[UUID] | None = Field(None, description="Associated model identifiers")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    pending_status: str | None = Field(None, description="Pending soft_calls_entry status (e.g. 'pending')")
    pending_operation: str | None = Field(None, description="Pending operation (create/update/delete/duplicate)")
    pending_call_id: UUID | None = Field(None, description="Originating tool call id for ack")


class ListProviderApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    providers: list[ListProviderApiProvider] | None = Field(None, description="List of provider entries")
    department_filter: ListFilterSection | None = Field(None, description="Department filter options")
    model_filter: ListFilterSection | None = Field(None, description="Model filter options")
    status_filter: ListFilterSection | None = Field(None, description="Status filter options")
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
    total_count: int | None = Field(None, description="Total number of providers")
    import_fields: list[ImportField] | None = Field(
        None, description="CSV import column schema for the bulk-import dialog"
    )


# ========== Shared Create/Update Types ==========


class ProviderFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class ProviderResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    provider_id: UUID | None = Field(None, description="Provider unique identifier")
    message: str = Field(..., description="Result message")
    errors: list[ProviderFieldError] | None = Field(None, description="List of field-level errors")


# ========== Create Endpoint Types ==========


class CreateProviderItem(ScopedItem):
    """Single provider item for create — no provider_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Client-provided UUID for the new provider")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required pair (one side must be set on create) — see
    # ``permissions_context.py::resolve_provider_values`` for the
    # runtime check. Descriptions flag this so the OpenAPI schema
    # consumed by LLM tool callers makes the constraint explicit.
    name_id: UUID | None = Field(
        None,
        description="REQUIRED FOR CREATE (or pass ``name``). UUID of an existing name resource.",
    )
    name: str | None = Field(
        None,
        description="REQUIRED FOR CREATE (or pass ``name_id``). Display name text — creates a new name resource on the fly.",
    )
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # Canonical flag ids + denormalized bool
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Denormalized provider_active flag state")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    # ID-only fields
    endpoint_ids: list[UUID] | None = Field(None, description="Endpoint resource identifiers")
    key_ids: list[UUID] | None = Field(None, description="API key resource identifiers")
    value_id: UUID | None = Field(None, description="Value resource identifier")
    # Direct value fields (for denormalized snapshot)
    endpoint: str | None = Field(None, description="Provider API endpoint URL")
    key: str | None = Field(None, description="Provider API key")
    value: str | None = Field(None, description="Provider identifier value")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "flag_ids": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "endpoint_ids": "endpoints",
        "key_ids": "keys",
        "value_id": "values",
    }


class CreateProviderApiRequest(BaseModel):
    """Request model for bulk create provider endpoint."""

    providers: list[CreateProviderItem] = Field(..., description="List of providers to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateProviderApiResponse(BaseModel):
    """Response model for bulk create provider endpoint."""

    results: list[ProviderResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # Full row content for each successfully-created provider — same
    # shape ``/provider/search`` returns. The audit framework spreads
    # response fields into the wire payload, so the client's ghost
    # rail can materialize the new row directly from
    # ``provider.create.completed`` without an SSR refresh round-trip.
    providers: list[ListProviderApiProvider] | None = Field(
        None, description="Hydrated rows for the successfully-created providers (mirrors /provider/search shape)",
    )


# ========== Update Endpoint Types ==========


class UpdateProviderItem(ScopedItem):
    """Single provider item for update — provider_id required, all fields optional."""

    id: UUID = Field(..., description="Target provider identifier to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    # Canonical flag ids + denormalized bool
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Denormalized provider_active flag state")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    # ID-only fields
    endpoint_ids: list[UUID] | None = Field(None, description="Endpoint resource identifiers")
    key_ids: list[UUID] | None = Field(None, description="API key resource identifiers")
    value_id: UUID | None = Field(None, description="Value resource identifier")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateProviderItem.RESOURCE_TYPE_MAP


class UpdateProviderPatch(UpdateProviderItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateProviderItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved provider id per matched row",
    )


class UpdateProviderApiRequest(BaseModel):
    """Request model for bulk update provider endpoint.

    Three body shapes:
      - First call (explicit): ``providers`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/provider/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    providers: list[UpdateProviderItem] | None = Field(
        None, description="List of providers to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteProviderApiRequest;
    # ``patch`` is the shared change set applied to every matched row.
    # ``patch.id`` is ignored — each resolved id is stamped onto a
    # clone before the per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every provider matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateProviderPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    filter_model_ids: list[UUID] | None = Field(None, description="Filter by model UUIDs")
    filter_status: list[str] | None = Field(None, description="Filter by status values (active/inactive)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    model_search: str | None = Field(None, description="Search text for model facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateProviderApiResponse(BaseModel):
    """Response model for bulk update provider endpoint."""

    results: list[ProviderResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # See CreateProviderApiResponse.providers — same role here for updates.
    providers: list[ListProviderApiProvider] | None = Field(
        None, description="Hydrated rows for the successfully-updated providers (mirrors /provider/search shape)",
    )


class SaveProviderFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class DeleteProviderApiRequest(BaseModel):
    """Request model for bulk delete provider endpoint.

    Three body shapes:
      - First call (explicit): ``provider_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/provider/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    provider_ids: list[UUID] | None = Field(
        None, description="UUIDs of providers to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchProviderApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every provider matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /provider/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``provider_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    filter_model_ids: list[UUID] | None = Field(None, description="Filter by model UUIDs")
    filter_status: list[str] | None = Field(None, description="Filter by status values (active/inactive)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    model_search: str | None = Field(None, description="Search text for model facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool | None = Field(None, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteProviderResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    provider_id: UUID | None = Field(None, description="Deleted provider identifier (None for soft-skipped not-found rows under ``all=true``)")
    message: str = Field(..., description="Result message")


class DeleteProviderApiResponse(BaseModel):
    """Response model for bulk delete provider endpoint."""

    results: list[DeleteProviderResult] = Field(..., description="List of deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateProviderApiRequest(BaseModel):
    """Request model for duplicate provider endpoint.

    Canonical shape: ``id`` (matches DuplicatePersonaApiRequest). The legacy
    ``provider_id`` field is preserved for backwards compatibility with older
    clients but ``id`` is preferred.
    """

    id: UUID | None = Field(None, description="UUID of the provider to duplicate")
    provider_id: UUID | None = Field(None, description="Legacy alias for id — prefer id")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateProviderApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    provider_id: UUID = Field(..., description="New duplicated provider identifier")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # See CreateProviderApiResponse.providers — single-element list
    # here (duplicate creates exactly one row), but kept as a list for
    # shape consistency across create/duplicate/update on the wire.
    providers: list[ListProviderApiProvider] | None = Field(
        None, description="Hydrated row for the newly-created duplicate provider (mirrors /provider/search shape)",
    )


# ========== Draft Endpoint Types (composable infra) ==========


class PatchProviderDraftApiRequest(ScopedItem):
    """Request model for new-style provider draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_id, department_ids, endpoint_ids, key_ids, value_id

    Client always sends full state (append-only — each write is a new snapshot).
    """

    draft_id: UUID | None = Field(None, description="Existing draft ID to update")
    input_draft_id: UUID | None = Field(None, description="Legacy alias for existing draft ID to update")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="Name resource identifier")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="Description resource identifier")

    # Canonical flag ids + denormalized bool resolved server-side
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical")
    active: bool | None = Field(None, description="Denormalized provider_active flag state; resolved to a flag_ids entry server-side")
    departments: list[str] | None = Field(None, description="Department names to match")
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    endpoint: str | None = Field(None, description="Provider endpoint URL")
    endpoint_id: UUID | None = Field(None, description="Endpoint resource identifier")
    endpoint_ids: list[UUID] | None = Field(None, description="Endpoint resource identifiers")
    key: str | None = Field(None, description="Provider key value")
    key_name: str | None = Field(None, description="Provider key display name")
    key_description: str | None = Field(None, description="Provider key description")
    key_id: UUID | None = Field(None, description="Key resource identifier")
    key_ids: list[UUID] | None = Field(None, description="API key resource identifiers")
    value: str | None = Field(None, description="Provider identifier value")
    value_id: UUID | None = Field(None, description="Value resource identifier")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers to preserve")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack semantics")
    accept: bool | None = Field(None, description="Accept or reject acknowledgement when idempotency_key is supplied")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "departments": "departments",
        "department_ids": "departments",
        "endpoint": "endpoints",
        "endpoint_id": "endpoints",
        "endpoint_ids": "endpoints",
        "key": "keys",
        "key_name": "keys",
        "key_description": "keys",
        "key_id": "keys",
        "key_ids": "keys",
        "value": "values",
        "value_id": "values",
    }


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource identifier")
    name: str | None = Field(None, description="Resolved name value")
    description_id: UUID | None = Field(None, description="Resolved description resource identifier")
    description: str | None = Field(None, description="Resolved description value")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed provider_active flag state")
    departments: list[str] = Field(default_factory=list, description="Resolved department names")
    department_ids: list[UUID] = Field(..., description="Department identifiers")
    endpoint: str | None = Field(None, description="Resolved endpoint value")
    endpoint_id: UUID | None = Field(None, description="Resolved endpoint resource identifier")
    endpoint_ids: list[UUID] = Field(..., description="Endpoint resource identifiers")
    key: str | None = Field(None, description="Resolved key value")
    key_name: str | None = Field(None, description="Resolved key display name")
    key_description: str | None = Field(None, description="Resolved key description")
    key_id: UUID | None = Field(None, description="Resolved key resource identifier")
    key_ids: list[UUID] = Field(..., description="API key resource identifiers")
    value: str | None = Field(None, description="Resolved value")
    value_id: UUID | None = Field(None, description="Value resource identifier")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


ProviderDraftFormState = DraftFormState


class PatchProviderDraftApiResponse(BaseModel):
    """Response model for new-style provider draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="Draft unique identifier")
    idempotency_key: UUID | None = Field(None, description="Operation key echoed back for client correlation")
    message: str = Field(..., description="Result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


class GetProviderDraftsApiRequest(BaseModel):
    """Request model for the provider drafts list endpoint.

    Mirrors ``GenerationsProviderApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GetProviderDraftsApiResponse(BaseModel):
    """Response model for provider drafts list endpoint."""

    entries: list[GetProviderDraftResponse] | None = Field(None, description="List of provider draft entries")


# ========== Export Endpoint Types ==========


class ExportProviderApiRequest(BaseModel):
    """Request model for provider export."""

    provider_id: UUID | None = Field(None, description="Provider identifier to export")
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")


class ExportProviderApiResponse(BaseModel):
    """Response model for export provider endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource holding the export CSV")
    file_name: str = Field(..., description="Suggested download file name")
    row_count: int = Field(..., description="Number of data rows in the export")


class FileDownloadProviderApiRequest(BaseModel):
    """Request model for provider file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadProviderApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# ========== Decrypt Endpoint Types ==========


class DecryptProviderKeyApiRequest(BaseModel):
    """Request to decrypt a key scoped to a provider."""

    provider_id: UUID = Field(..., description="Provider that owns the key")
    key_id: UUID = Field(..., description="Key identifier to decrypt")


class DecryptProviderKeyApiResponse(BaseModel):
    """Decrypted key response."""

    key: str | None = Field(None, description="Decrypted API key value")
    name: str | None = Field(None, description="Key display name")
    actor_name: str | None = Field(None, description="Display name of the current actor")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsProviderApiRequest(BaseModel):
    """Request model for provider generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GenerationsProviderListItem(BaseModel):
    """Single generation group in the provider generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsProviderApiResponse(BaseModel):
    """Response model for provider generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsProviderListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemProviderApiRequest(BaseModel):
    """Request model for provider problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemProviderApiResponse(BaseModel):
    """Response model for provider problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadProviderApiRequest(BaseModel):
    """Request model for provider text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadProviderApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadProviderApiRequest(BaseModel):
    """Request model for provider call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadProviderApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
