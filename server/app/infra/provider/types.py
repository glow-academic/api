"""Handcrafted types for provider artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.provider.create import CreateProviderItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.provider_drafts.types import GetProviderDraftResponse


class ProviderFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="Option ID to use when enabling")
    show: bool = Field(True, description="Whether to display this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this flag was AI-generated")


class ProviderNameSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected name resource")
    resources: list[Any] | None = Field(None, description="Available name resources")


class ProviderDescriptionSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected description resource")
    resources: list[Any] | None = Field(None, description="Available description resources")


class ProviderFlagSection(BaseResourceSection):
    current: list[ProviderFlagConfig] | None = Field(None, description="Currently active flag configs")
    resources: list[ProviderFlagConfig] | None = Field(None, description="Available flag configs")


class ProviderDepartmentSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently assigned departments")
    resources: list[Any] | None = Field(None, description="Available departments")


class ProviderValueSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected value resource")
    resources: list[Any] | None = Field(None, description="Available value resources")


class ProviderEndpointSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected endpoint resource")
    resources: list[Any] | None = Field(None, description="Available endpoint resources")


class ProviderKeySection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected key resource")
    resources: list[Any] | None = Field(None, description="Available key resources")


class GetProviderApiRequest(BaseModel):
    """Request model for get provider endpoint."""

    provider_id: UUID | None = Field(None, description="Provider unique identifier")
    draft_id: UUID | None = Field(None, description="Draft unique identifier")


class GetProviderApiResponse(BaseModel):
    """Section-first response for provider editor."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    provider_exists: bool | None = Field(None, description="Whether the provider exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Group identifier for the provider")

    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    integrations_show_ai_generate: bool | None = Field(None, description="Show AI generate for integrations step")

    names: ProviderNameSection | None = Field(None, description="Name section with resources")
    descriptions: ProviderDescriptionSection | None = Field(None, description="Description section with resources")
    flags: ProviderFlagSection | None = Field(None, description="Flag section with configs")
    departments: ProviderDepartmentSection | None = Field(None, description="Department section with resources")
    values: ProviderValueSection | None = Field(None, description="Value section with resources")
    endpoints: ProviderEndpointSection | None = Field(None, description="Endpoint section with resources")
    keys: ProviderKeySection | None = Field(None, description="Key section with resources")


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


class CreateProviderApiRequest(BaseModel):
    """Request model for bulk create provider endpoint."""

    providers: list[CreateProviderItem] = Field(..., description="List of providers to create")


class CreateProviderApiResponse(BaseModel):
    """Response model for bulk create provider endpoint."""

    results: list[ProviderResultItem] = Field(..., description="List of operation results")


# ========== Update Endpoint Types ==========


class UpdateProviderItem(BaseModel):
    """Single provider item for update — provider_id required, all fields optional."""

    provider_id: UUID = Field(..., description="Target provider identifier to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Display name value")
    description_id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Description text value")
    active_flag_id: UUID | None = Field(None, description="Active flag option identifier")
    active_flag: bool | None = Field(None, description="Whether the provider is active")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    departments: list[str] | None = Field(None, description="Department names to match")
    # ID-only fields
    endpoint_ids: list[UUID] | None = Field(None, description="Endpoint resource identifiers")
    key_ids: list[UUID] | None = Field(None, description="API key resource identifiers")
    value_ids: list[UUID] | None = Field(None, description="Value resource identifiers")


class UpdateProviderApiRequest(BaseModel):
    """Request model for bulk update provider endpoint."""

    providers: list[UpdateProviderItem] = Field(..., description="List of providers to update")


class UpdateProviderApiResponse(BaseModel):
    """Response model for bulk update provider endpoint."""

    results: list[ProviderResultItem] = Field(..., description="List of operation results")


class SaveProviderFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message describing the issue")


class DeleteProviderApiRequest(BaseModel):
    """Request model for bulk delete provider endpoint."""

    provider_ids: list[UUID] = Field(..., description="List of provider IDs to delete")


class DeleteProviderResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    provider_id: UUID = Field(..., description="Deleted provider identifier")
    message: str = Field(..., description="Result message")


class DeleteProviderApiResponse(BaseModel):
    """Response model for bulk delete provider endpoint."""

    results: list[DeleteProviderResult] = Field(..., description="List of deletion results")


class DuplicateProviderApiRequest(BaseModel):
    provider_id: UUID = Field(..., description="Provider identifier to duplicate")


class DuplicateProviderApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    provider_id: UUID = Field(..., description="New duplicated provider identifier")
    message: str = Field(..., description="Result message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchProviderDraftApiRequest(BaseModel):
    """Request model for new-style provider draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_id, department_ids, endpoint_ids, key_ids, value_ids

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
    flag_id: UUID | None = Field(None, description="Flag option identifier")
    department_ids: list[UUID] | None = Field(None, description="Department identifiers")
    endpoint_ids: list[UUID] | None = Field(None, description="Endpoint resource identifiers")
    key_ids: list[UUID] | None = Field(None, description="API key resource identifiers")
    value_ids: list[UUID] | None = Field(None, description="Value resource identifiers")


class ProviderDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource identifier")
    description_id: UUID | None = Field(None, description="Resolved description resource identifier")
    flag_id: UUID | None = Field(None, description="Flag option identifier")
    department_ids: list[UUID] = Field(..., description="Department identifiers")
    endpoint_ids: list[UUID] = Field(..., description="Endpoint resource identifiers")
    key_ids: list[UUID] = Field(..., description="API key resource identifiers")
    value_ids: list[UUID] = Field(..., description="Value resource identifiers")


class PatchProviderDraftApiResponse(BaseModel):
    """Response model for new-style provider draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="Draft unique identifier")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Result message")
    form_state: ProviderDraftFormState | None = Field(None, description="Server-authoritative form state")


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
