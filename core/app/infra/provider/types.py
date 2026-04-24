"""Handcrafted types for provider artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
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
    updated_at: datetime | None = Field(None, description="Timestamp of last update")
    department_ids: list[UUID] | None = Field(None, description="Associated department identifiers")
    model_usage_count: int | None = Field(None, description="Number of models using this provider")
    model_ids: list[UUID] | None = Field(None, description="Associated model identifiers")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")


class ListProviderApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the current actor")
    providers: list[ListProviderApiProvider] | None = Field(None, description="List of provider entries")
    department_filter: ListFilterSection | None = Field(None, description="Department filter options")
    model_filter: ListFilterSection | None = Field(None, description="Model filter options")
    status_filter: ListFilterSection | None = Field(None, description="Status filter options")
    total_count: int | None = Field(None, description="Total number of providers")


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
    """Single provider item for create — no provider_id."""

    id: UUID | None = Field(None, description="Optional pre-assigned identifier")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
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
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateProviderApiResponse(BaseModel):
    """Response model for bulk create provider endpoint."""

    results: list[ProviderResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


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


class UpdateProviderApiRequest(BaseModel):
    """Request model for bulk update provider endpoint."""

    providers: list[UpdateProviderItem] = Field(..., description="List of providers to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateProviderApiResponse(BaseModel):
    """Response model for bulk update provider endpoint."""

    results: list[ProviderResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveProviderFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class DeleteProviderApiRequest(BaseModel):
    """Request model for bulk delete provider endpoint."""

    provider_ids: list[UUID] = Field(..., description="List of provider IDs to delete")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteProviderResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    provider_id: UUID = Field(..., description="Deleted provider identifier")
    message: str = Field(..., description="Result message")


class DeleteProviderApiResponse(BaseModel):
    """Response model for bulk delete provider endpoint."""

    results: list[DeleteProviderResult] = Field(..., description="List of deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateProviderApiRequest(BaseModel):
    provider_id: UUID = Field(..., description="Provider identifier to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateProviderApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    provider_id: UUID = Field(..., description="New duplicated provider identifier")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


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
    accept: bool = Field(True, description="Accept or reject acknowledgement when idempotency_key is supplied")

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


class GetProviderDraftsApiResponse(BaseModel):
    """Response model for provider drafts list endpoint."""

    entries: list[GetProviderDraftResponse] | None = Field(None, description="List of provider draft entries")


# ========== Export Endpoint Types ==========


class ExportProviderApiRequest(BaseModel):
    """Request model for provider export."""

    provider_id: UUID | None = Field(None, description="Provider identifier to export")


class ExportProviderApiResponse(BaseModel):
    """Response model for export provider endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


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
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemProviderApiResponse(BaseModel):
    """Response model for provider problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
