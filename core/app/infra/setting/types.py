"""Handcrafted types for settings artifact — GET, SAVE, DRAFT, LIST, DELETE, DUPLICATE."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.infra.setting.create import CreateSettingItem
from app.infra.v5_types import BaseResourceSection
from app.tools.entries.setting_drafts.types import GetSettingDraftResponse

# ========== Flag Enrichment ==========


class SettingFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier (e.g. 'active')")
    label: str = Field(..., description="Human-readable flag label (e.g. 'Active')")
    description: str | None = Field(None, description="Flag description text")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="UUID of the flag option to use when enabling")
    show: bool = Field(True, description="Whether the flag is visible to the client")
    required: bool = Field(False, description="Whether the flag is required")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")


# ========== Per-Resource Section Types ==========


# Single-select sections
class SettingNameSection(BaseResourceSection):
    resource: dict | None = Field(None, description="Currently selected name resource")
    resources: list | None = Field(None, description="Available name resources")


class SettingDescriptionSection(BaseResourceSection):
    resource: dict | None = Field(None, description="Currently selected description resource")
    resources: list | None = Field(None, description="Available description resources")


# Flag section (uses SettingFlagConfig)
class SettingFlagSection(BaseResourceSection):
    current: SettingFlagConfig | None = Field(None, description="Currently selected flag config")
    resources: list[SettingFlagConfig] | None = Field(None, description="Available flag configs")


# Multi-select sections
class SettingColorSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned colors")
    resources: list | None = Field(None, description="Available color resources")


class SettingDepartmentSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned departments")
    resources: list | None = Field(None, description="Available department resources")


class SettingProfileSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned profiles")
    resources: list | None = Field(None, description="Available profile resources")


class SettingAuthSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned auth providers")
    resources: list | None = Field(None, description="Available auth resources")


class SettingProviderKeySection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned provider keys")
    resources: list | None = Field(None, description="Available provider key resources")


class SettingAuthItemKeySection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned auth item keys")
    resources: list | None = Field(None, description="Available auth item key resources")


class SettingSystemSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned systems")
    resources: list | None = Field(None, description="Available system resources")


# ========== GET Endpoint Types ==========


class GetSettingApiRequest(BaseModel):
    """Request model for get setting endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    setting_id: UUID | None = Field(default=None, alias="settings_id", description="UUID of the setting to retrieve")
    color_search: str | None = Field(None, description="Search query for color resources")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")
    mcp: bool | None = Field(False, description="Whether request is from MCP client")


class GetSettingApiResponse(BaseModel):
    """Section-first response model for get setting endpoint."""

    # Context
    actor_name: str | None = Field(None, description="Display name of the acting user")
    setting_exists: bool | None = Field(None, description="Whether the setting exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this setting")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")

    # Per-resource sections (10 total)
    names: SettingNameSection | None = Field(None, description="Name section with resources")
    descriptions: SettingDescriptionSection | None = Field(None, description="Description section with resources")
    colors: SettingColorSection | None = Field(None, description="Color section with resources")
    flags: SettingFlagSection | None = Field(None, description="Flag section with configs")
    departments: SettingDepartmentSection | None = Field(None, description="Department section with resources")
    profiles: SettingProfileSection | None = Field(None, description="Profile section with resources")
    auths: SettingAuthSection | None = Field(None, description="Auth section with resources")
    provider_keys: SettingProviderKeySection | None = Field(None, description="Provider key section with resources")
    auth_item_keys: SettingAuthItemKeySection | None = Field(None, description="Auth item key section with resources")
    systems: SettingSystemSection | None = Field(None, description="System section with resources")


# ========== Generation Completion Event ==========


class SettingGenerationCompleteEvent(BaseModel):
    """Typed event emitted on socket generation completion."""

    artifact_type: str = Field("setting", description="Type of artifact being generated")
    resource_type: str = Field(..., description="Type of resource that was generated")
    run_id: str | None = Field(None, description="UUID of the generation run")
    group_id: str | None = Field(None, description="Group UUID for the generation")
    success: bool = Field(False, description="Whether the generation succeeded")


# ========== Shared Save/Create/Update Types ==========


class SettingFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class SettingResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    setting_id: UUID | None = Field(None, description="UUID of the created or updated setting")
    message: str = Field(..., description="Result message")
    errors: list[SettingFieldError] | None = Field(None, description="Per-field validation errors")


# ========== Create Endpoint Types ==========


class CreateSettingApiRequest(BaseModel):
    """Request model for bulk create setting endpoint."""

    settings: list[CreateSettingItem] = Field(..., description="List of settings to create")


class CreateSettingApiResponse(BaseModel):
    """Response model for bulk create setting endpoint."""

    results: list[SettingResultItem] = Field(..., description="Per-item creation results")


# ========== Update Endpoint Types ==========


class UpdateSettingItem(BaseModel):
    """Single setting item for update — setting_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    setting_id: UUID = Field(..., description="UUID of the setting to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    # Optional flag
    active_flag_id: UUID | None = Field(None, description="UUID of the active flag option")
    active_flag: bool | None = Field(None, description="Whether the setting is active")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    color_ids: list[UUID] | None = Field(None, description="Color resource UUIDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs to assign")
    auth_ids: list[UUID] | None = Field(None, description="Auth provider UUIDs")
    provider_key_ids: list[UUID] | None = Field(None, description="Provider key UUIDs")
    auth_item_key_ids: list[UUID] | None = Field(None, description="Auth item key UUIDs")
    auth_item_value_ids: list[UUID] | None = Field(None, description="Auth item value UUIDs")
    system_ids: list[UUID] | None = Field(None, description="System UUIDs to assign")
    threshold_ids: list[UUID] | None = Field(None, description="Threshold UUIDs to assign")
    setting_resource_ids: list[UUID] | None = Field(None, description="Setting resource UUIDs")


class UpdateSettingApiRequest(BaseModel):
    """Request model for bulk update setting endpoint."""

    settings: list[UpdateSettingItem] = Field(..., description="List of settings to update")


class UpdateSettingApiResponse(BaseModel):
    """Response model for bulk update setting endpoint."""

    results: list[SettingResultItem] = Field(..., description="Per-item update results")


class SaveSettingFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchSettingDraftApiRequest(BaseModel):
    """Request model for new-style setting draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_id, department_ids, color_ids, profile_ids, auth_ids,
        provider_key_ids, auth_item_key_ids, threshold_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    expected_version: int = Field(0, description="Expected draft version for optimistic locking")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to resolve or create")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    # Non-creatable — ID-only
    flag_id: UUID | None = Field(None, description="UUID of the flag option")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    color_ids: list[UUID] | None = Field(None, description="Color resource UUIDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs to assign")
    auth_ids: list[UUID] | None = Field(None, description="Auth provider UUIDs")
    provider_key_ids: list[UUID] | None = Field(None, description="Provider key UUIDs")
    auth_item_key_ids: list[UUID] | None = Field(None, description="Auth item key UUIDs")
    threshold_ids: list[UUID] | None = Field(None, description="Threshold UUIDs to assign")


class SettingDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    flag_id: UUID | None = Field(None, description="Resolved flag option UUID")
    department_ids: list[UUID] = Field(..., description="Assigned department UUIDs")
    color_ids: list[UUID] = Field(..., description="Assigned color UUIDs")
    profile_ids: list[UUID] = Field(..., description="Assigned profile UUIDs")
    auth_ids: list[UUID] = Field(..., description="Assigned auth provider UUIDs")
    provider_key_ids: list[UUID] = Field(..., description="Assigned provider key UUIDs")
    auth_item_key_ids: list[UUID] = Field(..., description="Assigned auth item key UUIDs")
    threshold_ids: list[UUID] = Field(..., description="Assigned threshold UUIDs")


class PatchSettingDraftApiResponse(BaseModel):
    """Response model for new-style setting draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Result message")
    form_state: SettingDraftFormState | None = Field(None, description="Server-authoritative form state")


class GetSettingDraftsApiResponse(BaseModel):
    """Response model for setting drafts list endpoint."""

    entries: list[GetSettingDraftResponse] | None = Field(None, description="List of setting draft entries")


# ========== List Endpoint Types ==========


class ListSettingApiSetting(BaseModel):
    """Setting type for list endpoint with computed permissions."""

    settings_id: UUID | None = Field(None, description="Unique setting identifier")
    created_at: datetime | None = Field(None, description="Timestamp when setting was created")
    active: bool | None = Field(None, description="Whether the setting is currently active")
    name: str | None = Field(None, description="Setting display name")
    description: str | None = Field(None, description="Setting description text")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    # Computed in Python
    can_edit: bool | None = Field(None, description="Whether the actor can edit this setting")
    can_delete: bool | None = Field(None, description="Whether the actor can delete this setting")
    can_duplicate: bool | None = Field(None, description="Whether the actor can duplicate this setting")


class ListSettingApiKey(BaseModel):
    """Key type for list endpoint."""

    key_id: UUID | None = Field(None, description="Unique key identifier")
    name: str | None = Field(None, description="Key display name")
    key_masked: str | None = Field(None, description="Masked key value for display")
    description: str | None = Field(None, description="Key description text")
    active: bool | None = Field(None, description="Whether the key is currently active")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")


class ListSettingApiResponse(BaseModel):
    """Response model for list setting endpoint."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    user_role: str | None = Field(None, description="Role of the acting user")
    settings: list[ListSettingApiSetting] | None = Field(None, description="List of setting items")
    keys: list[ListSettingApiKey] | None = Field(None, description="List of key items")


# ========== Delete Endpoint Types ==========


class DeleteSettingApiRequest(BaseModel):
    """Request model for bulk delete setting endpoint."""

    setting_ids: list[UUID] = Field(..., description="UUIDs of settings to delete")


class DeleteSettingResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    setting_id: UUID = Field(..., description="UUID of the deleted setting")
    message: str = Field(..., description="Result message")


class DeleteSettingApiResponse(BaseModel):
    """Response model for bulk delete setting endpoint."""

    results: list[DeleteSettingResult] = Field(..., description="Per-item deletion results")


# ========== Duplicate Endpoint Types ==========


class DuplicateSettingApiRequest(BaseModel):
    """Request model for duplicate setting endpoint."""

    setting_id: UUID = Field(..., description="UUID of the setting to duplicate")


class DuplicateSettingApiResponse(BaseModel):
    """Response model for duplicate setting endpoint."""

    success: bool = Field(..., description="Whether the duplication succeeded")
    setting_id: UUID = Field(..., description="UUID of the newly created setting")
    message: str = Field(..., description="Result message")


# ========== Export Endpoint Types ==========


class ExportSettingApiRequest(BaseModel):
    """Request model for setting export."""

    setting_id: UUID | None = Field(None, description="UUID of the setting to export")


class ExportSettingApiResponse(BaseModel):
    """Response model for export setting endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


# ========== Decrypt Endpoint Types ==========


class DecryptSettingKeyApiRequest(BaseModel):
    """Request to decrypt a key scoped to a setting."""

    setting_id: UUID = Field(..., description="UUID of the parent setting")
    key_id: UUID = Field(..., description="UUID of the key to decrypt")


class DecryptSettingKeyApiResponse(BaseModel):
    """Decrypted key response."""

    key: str | None = Field(None, description="Decrypted key value")
    name: str | None = Field(None, description="Key display name")
    actor_name: str | None = Field(None, description="Display name of the acting user")
