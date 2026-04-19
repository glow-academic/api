"""Handcrafted types for settings artifact — GET, SAVE, DRAFT, LIST, DELETE, DUPLICATE."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.setting_drafts.types import GetSettingDraftResponse

class SettingNameResource(BaseModel):
    id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Setting display name")
    generated: bool | None = Field(None, description="Whether the name was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingDescriptionResource(BaseModel):
    id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Setting description")
    generated: bool | None = Field(None, description="Whether the description was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingColorResource(BaseModel):
    id: UUID | None = Field(None, description="Color resource identifier")
    name: str | None = Field(None, description="Color display name")
    description: str | None = Field(None, description="Color description")
    hex_code: str | None = Field(None, description="Hex color value")
    generated: bool | None = Field(None, description="Whether the color was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingFlagConfig(BaseModel):
    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description text")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="UUID of the flag option to use when enabling")
    show: bool = Field(True, description="Whether the flag is visible to the client")
    required: bool = Field(False, description="Whether the flag is required")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingDepartmentResource(BaseModel):
    department_id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether the department was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingProfileResource(BaseModel):
    profile_id: UUID | None = Field(None, description="Profile identifier")
    name: str | None = Field(None, description="Profile display name")
    description: str | None = Field(None, description="Profile description")
    generated: bool | None = Field(None, description="Whether the profile was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingAuthResource(BaseModel):
    auth_id: UUID | None = Field(None, description="Auth identifier")
    name: str | None = Field(None, description="Auth display name")
    description: str | None = Field(None, description="Auth description")
    slug: str | None = Field(None, description="Auth slug")
    protocol: str | None = Field(None, description="Auth protocol")
    generated: bool | None = Field(None, description="Whether the auth was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingProviderKeyResource(BaseModel):
    id: UUID | None = Field(None, description="Provider key identifier")
    provider_id: UUID | None = Field(None, description="Provider identifier")
    key_id: UUID | None = Field(None, description="Key identifier")
    key: str | None = Field(None, description="Key value")
    name: str | None = Field(None, description="Key display name")
    description: str | None = Field(None, description="Key description")
    generated: bool | None = Field(None, description="Whether the provider-key pair was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingAuthItemKeyResource(BaseModel):
    id: UUID | None = Field(None, description="Auth item key identifier")
    auth_id: UUID | None = Field(None, description="Auth identifier")
    item_id: UUID | None = Field(None, description="Item identifier")
    key_id: UUID | None = Field(None, description="Key identifier")
    generated: bool | None = Field(None, description="Whether the auth-item-key pair was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingSystemResource(BaseModel):
    system_id: UUID | None = Field(None, description="System identifier")
    name: str | None = Field(None, description="System display name")
    description: str | None = Field(None, description="System description")
    agent_ids: list[UUID] = Field(default_factory=list, description="Linked agent identifiers")
    resolution_strategy: str | None = Field(None, description="Resolution strategy")
    resolution_threshold: float | None = Field(None, description="Resolution threshold")
    generated: bool | None = Field(None, description="Whether the system was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingProviderCatalogResource(BaseModel):
    provider_id: UUID | None = Field(None, description="Provider identifier")
    name: str | None = Field(None, description="Provider display name")
    description: str | None = Field(None, description="Provider description")


class SettingKeyCatalogResource(BaseModel):
    key_id: UUID | None = Field(None, description="Key identifier")
    name: str | None = Field(None, description="Key display name")
    description: str | None = Field(None, description="Key description")
    masked_key: str | None = Field(None, description="Masked key value for display")


class SectionFilter(BaseModel):
    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")
    parameter_ids: list[str] | None = Field(None, description="Reserved for compatibility with shared filter parsing")


class GetSettingApiRequest(BaseModel):
    """Request model for get setting endpoint."""

    id: UUID | None = Field(None, description="UUID of the setting to retrieve")
    setting_id: UUID | None = Field(None, description="Legacy setting identifier")
    settings_id: UUID | None = Field(None, description="Legacy alias for setting identifier")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions")
    colors: SectionFilter | None = Field(None, description="Filter options for colors")
    flags: SectionFilter | None = Field(None, description="Filter options for flags")
    departments: SectionFilter | None = Field(None, description="Filter options for departments")
    profiles: SectionFilter | None = Field(None, description="Filter options for profiles")
    auths: SectionFilter | None = Field(None, description="Filter options for auths")
    provider_keys: SectionFilter | None = Field(None, description="Filter options for provider keys")
    auth_item_keys: SectionFilter | None = Field(None, description="Filter options for auth item keys")
    systems: SectionFilter | None = Field(None, description="Filter options for systems")


class GetSettingApiResponse(BaseModel):
    """Canonical composed setting response."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    setting_exists: bool | None = Field(None, description="Whether the setting exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this setting")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")
    show_ai_generate: bool | None = Field(None, description="Whether any section should show AI generate")
    basic_show_ai_generate: bool | None = Field(None, description="Whether the basic section should show AI generate")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[SettingNameResource] | None = Field(None, description="Name resources")
    descriptions: list[SettingDescriptionResource] | None = Field(None, description="Description resources")
    colors: list[SettingColorResource] | None = Field(None, description="Color resources")
    flags: list[SettingFlagConfig] | None = Field(None, description="Flag configs")
    departments: list[SettingDepartmentResource] | None = Field(None, description="Department resources")
    profiles: list[SettingProfileResource] | None = Field(None, description="Profile resources")
    auths: list[SettingAuthResource] | None = Field(None, description="Auth resources")
    provider_keys: list[SettingProviderKeyResource] | None = Field(None, description="Provider key resources")
    auth_item_keys: list[SettingAuthItemKeyResource] | None = Field(None, description="Auth item key resources")
    systems: list[SettingSystemResource] | None = Field(None, description="System resources")
    providers: list[SettingProviderCatalogResource] | None = Field(None, description="Provider catalog used by provider key editing")
    keys: list[SettingKeyCatalogResource] | None = Field(None, description="Key catalog used by provider key and auth item key editing")


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


class CreateSettingItem(ScopedItem):
    """Single setting item for create — no setting_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Optional preset UUID for the new setting artifact")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the settings_resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    # Optional single-select — provide ID or value
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

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "active_flag_id": "flags",
        "active_flag": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "color_ids": "colors",
        "profile_ids": "profiles",
        "auth_ids": "auths",
        "provider_key_ids": "provider_keys",
        "auth_item_key_ids": "auth_item_keys",
        "auth_item_value_ids": "auth_item_values",
        "system_ids": "systems",
        "threshold_ids": "thresholds",
        "setting_resource_ids": "setting_resources",
    }


class CreateSettingApiRequest(BaseModel):
    """Request model for bulk create setting endpoint."""

    settings: list[CreateSettingItem] = Field(..., description="List of settings to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateSettingApiResponse(BaseModel):
    """Response model for bulk create setting endpoint."""

    results: list[SettingResultItem] = Field(..., description="Per-item creation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateSettingItem(ScopedItem):
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

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateSettingItem.RESOURCE_TYPE_MAP


class UpdateSettingApiRequest(BaseModel):
    """Request model for bulk update setting endpoint."""

    settings: list[UpdateSettingItem] = Field(..., description="List of settings to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateSettingApiResponse(BaseModel):
    """Response model for bulk update setting endpoint."""

    results: list[SettingResultItem] = Field(..., description="Per-item update results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveSettingFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchSettingDraftApiRequest(ScopedItem):
    """Canonical setting draft request."""

    draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    input_draft_id: UUID | None = Field(None, description="Legacy draft UUID alias")
    idempotency_key: UUID | None = Field(None, description="Operation key for accept/reject acknowledgement")
    accept: bool = Field(True, description="Accept or reject pending draft state when used with idempotency_key")

    name: str | None = Field(None, description="Name value to resolve or create")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    active_flag: bool | None = Field(None, description="Whether the setting is active")
    active_flag_id: UUID | None = Field(None, description="UUID of the active flag option")
    flag_id: UUID | None = Field(None, description="Legacy alias for the active flag option")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    color_ids: list[UUID] | None = Field(None, description="Color resource UUIDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs to assign")
    auth_ids: list[UUID] | None = Field(None, description="Auth provider UUIDs")
    provider_key_ids: list[UUID] | None = Field(None, description="Provider key UUIDs")
    auth_item_key_ids: list[UUID] | None = Field(None, description="Auth item key UUIDs")
    system_ids: list[UUID] | None = Field(None, description="System UUIDs to assign")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to retain as pending inactive connections")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "active_flag": "flags",
        "active_flag_id": "flags",
        "flag_id": "flags",
        "departments": "departments",
        "department_ids": "departments",
        "color_ids": "colors",
        "profile_ids": "profiles",
        "auth_ids": "auths",
        "provider_key_ids": "provider_keys",
        "auth_item_key_ids": "auth_item_keys",
        "system_ids": "systems",
    }


class DraftFormState(BaseModel):
    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    name: str | None = Field(None, description="Echoed name value when available")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    description: str | None = Field(None, description="Echoed description value when available")
    active_flag_id: UUID | None = Field(None, description="Resolved active flag option UUID")
    flag_id: UUID | None = Field(None, description="Legacy alias for the active flag option UUID")
    department_ids: list[UUID] = Field(default_factory=list, description="Assigned department UUIDs")
    color_ids: list[UUID] = Field(default_factory=list, description="Assigned color UUIDs")
    profile_ids: list[UUID] = Field(default_factory=list, description="Assigned profile UUIDs")
    auth_ids: list[UUID] = Field(default_factory=list, description="Assigned auth provider UUIDs")
    provider_key_ids: list[UUID] = Field(default_factory=list, description="Assigned provider key UUIDs")
    auth_item_key_ids: list[UUID] = Field(default_factory=list, description="Assigned auth item key UUIDs")
    system_ids: list[UUID] = Field(default_factory=list, description="Assigned system UUIDs")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


class PatchSettingDraftApiResponse(BaseModel):
    """Response model for new-style setting draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    message: str = Field(..., description="Result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


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
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteSettingResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    setting_id: UUID = Field(..., description="UUID of the deleted setting")
    message: str = Field(..., description="Result message")


class DeleteSettingApiResponse(BaseModel):
    """Response model for bulk delete setting endpoint."""

    results: list[DeleteSettingResult] = Field(..., description="Per-item deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Duplicate Endpoint Types ==========


class DuplicateSettingApiRequest(BaseModel):
    """Request model for duplicate setting endpoint."""

    setting_id: UUID = Field(..., description="UUID of the setting to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateSettingApiResponse(BaseModel):
    """Response model for duplicate setting endpoint."""

    success: bool = Field(..., description="Whether the duplication succeeded")
    setting_id: UUID = Field(..., description="UUID of the newly created setting")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


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


# ========== Generations Types ==========


class GenerationsSettingApiRequest(BaseModel):
    """Request model for setting generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsSettingListItem(BaseModel):
    """Single generation group in the setting generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsSettingApiResponse(BaseModel):
    """Response model for setting generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsSettingListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# ========== Problem Types ==========


class ProblemSettingApiRequest(BaseModel):
    """Request model for setting problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemSettingApiResponse(BaseModel):
    """Response model for setting problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
