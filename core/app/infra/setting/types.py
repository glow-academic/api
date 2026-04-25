"""Handcrafted types for settings artifact — GET, SAVE, DRAFT, LIST, DELETE, DUPLICATE."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
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
    type: str | None = Field(None, description="Color role — 'primary', 'secondary', 'accent', etc.")
    generated: bool | None = Field(None, description="Whether the color was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'setting_active', 'mcp')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup (hydrated from icons_resource)")
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


class SettingMcpResource(BaseModel):
    mcp_id: UUID | None = Field(None, description="MCP resource identifier")
    agent_id: UUID | None = Field(None, description="Agent providing MCP tools")
    name: str | None = Field(None, description="MCP config display name")
    description: str | None = Field(None, description="MCP config description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingThresholdResource(BaseModel):
    id: UUID | None = Field(None, description="Threshold resource identifier")
    type: str | None = Field(None, description="Threshold type (e.g. 'success')")
    value: int | None = Field(None, description="Threshold integer value")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingAuthItemValueResource(BaseModel):
    id: UUID | None = Field(None, description="Auth item value identifier")
    auth_id: UUID | None = Field(None, description="Auth provider identifier")
    item_id: UUID | None = Field(None, description="Claim item identifier")
    value: str | None = Field(None, description="Literal claim value")
    generated: bool | None = Field(None, description="Whether the value was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingItemCatalogResource(BaseModel):
    item_id: UUID | None = Field(None, description="Claim item identifier")
    name: str | None = Field(None, description="Claim item display name (e.g. clientId)")
    description: str | None = Field(None, description="Claim item description")
    encrypted: bool | None = Field(None, description="Whether the item value must be stored encrypted")
    position: int | None = Field(None, description="Display ordering position")


class SettingProfileCatalogResource(BaseModel):
    profile_id: UUID | None = Field(None, description="Profile identifier")
    name: str | None = Field(None, description="Profile display name")
    description: str | None = Field(None, description="Profile description")


class SettingAuthCatalogResource(BaseModel):
    id: UUID | None = Field(None, description="Auth provider identifier (canonical for picker selection)")
    auth_id: UUID | None = Field(None, description="Auth provider identifier (alias for id)")
    name: str | None = Field(None, description="Auth display name")
    description: str | None = Field(None, description="Auth description")
    slug: str | None = Field(None, description="Auth slug")
    protocol: str | None = Field(None, description="Auth protocol")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingIconCatalogResource(BaseModel):
    icon_id: UUID | None = Field(None, description="Icon identifier")
    name: str | None = Field(None, description="Icon display name")
    description: str | None = Field(None, description="Icon description")
    value: str | None = Field(None, description="Icon value (SVG markup or slug)")


class SettingAgentCatalogResource(BaseModel):
    agent_id: UUID | None = Field(None, description="Agent identifier")
    name: str | None = Field(None, description="Agent display name")
    description: str | None = Field(None, description="Agent description")


class SettingProviderKeyOption(BaseModel):
    """Server-curated (provider × key) catalog option for the ProviderKeys picker."""

    provider_id: UUID | None = Field(None, description="Provider identifier")
    key_id: UUID | None = Field(None, description="Key identifier")
    provider_name: str | None = Field(None, description="Provider display name")
    key_name: str | None = Field(None, description="Key display name")
    masked_key: str | None = Field(None, description="Masked key value for display")


class SettingAuthItemKeyOption(BaseModel):
    """Server-curated (auth × item × key) catalog option for the AuthItemKeys picker."""

    auth_id: UUID | None = Field(None, description="Auth provider identifier")
    item_id: UUID | None = Field(None, description="Claim item identifier")
    key_id: UUID | None = Field(None, description="Key identifier")
    auth_name: str | None = Field(None, description="Auth display name")
    item_name: str | None = Field(None, description="Claim item display name")
    key_name: str | None = Field(None, description="Key display name")
    masked_key: str | None = Field(None, description="Masked key value for display")


class SettingAuthItemValueOption(BaseModel):
    """Server-curated (auth × item) catalog option for the AuthItemValues picker."""

    auth_id: UUID | None = Field(None, description="Auth provider identifier")
    item_id: UUID | None = Field(None, description="Claim item identifier")
    auth_name: str | None = Field(None, description="Auth display name")
    item_name: str | None = Field(None, description="Claim item display name")
    item_description: str | None = Field(None, description="Claim item description")
    encrypted: bool | None = Field(None, description="Whether the value must be stored encrypted")


class SettingMcpOption(BaseModel):
    """Server-curated per-agent catalog option for the MCP picker."""

    agent_id: UUID | None = Field(None, description="Agent identifier")
    agent_name: str | None = Field(None, description="Agent display name")
    agent_description: str | None = Field(None, description="Agent description")


class SettingProviderKeyDraftValue(BaseModel):
    """Draft value object for an inline-creatable (provider × key) pair.

    Two flows:
    - Create-by-value: caller supplies `key_value` (and optional `key_name`).
      Server encrypts it, creates a fresh `keys_resource` row, and links a
      `provider_keys_resource` row for (provider_id, new_key_id).
    - Re-link existing: caller supplies `key_id` referencing an existing
      `keys_resource` row. Server upserts the junction.
    """

    id: UUID | None = Field(None, description="Existing provider_keys_resource id when known")
    provider_id: UUID = Field(..., description="Provider identifier")
    key_id: UUID | None = Field(None, description="Existing keys_resource id (optional when key_value provided)")
    key_value: str | None = Field(None, description="Plaintext API key. Server encrypts and creates a keys_resource row.")
    key_name: str | None = Field(None, description="Optional display name for the new keys_resource row")


class SettingAuthItemKeyDraftValue(BaseModel):
    """Draft value object for an inline-creatable (auth × item × key) triple.

    Same two flows as SettingProviderKeyDraftValue: server encrypts
    `key_value` and creates a fresh `keys_resource` row when supplied.
    """

    id: UUID | None = Field(None, description="Existing auth_item_keys_resource id when known")
    auth_id: UUID = Field(..., description="Auth provider identifier")
    item_id: UUID = Field(..., description="Claim item identifier")
    key_id: UUID | None = Field(None, description="Existing keys_resource id (optional when key_value provided)")
    key_value: str | None = Field(None, description="Plaintext key/secret. Server encrypts and creates a keys_resource row.")
    key_name: str | None = Field(None, description="Optional display name for the new keys_resource row")


class SettingAuthItemValueDraftValue(BaseModel):
    """Draft value object for an inline-creatable (auth × item × value) triple."""

    id: UUID | None = Field(None, description="Existing auth_item_values_resource id when known")
    auth_id: UUID = Field(..., description="Auth provider identifier")
    item_id: UUID = Field(..., description="Claim item identifier")
    value: str = Field(..., description="Literal claim value")


class SettingMcpDraftValue(BaseModel):
    """Draft value object for an inline-creatable mcp row."""

    id: UUID | None = Field(None, description="Existing mcp_resource id when known")
    agent_id: UUID = Field(..., description="Agent identifier")
    name: str | None = Field(None, description="Optional display name — defaults to agent.name")
    description: str | None = Field(None, description="Optional description")


class SettingSystemDraftValue(BaseModel):
    """Draft value object for an inline-creatable systems_resource row."""

    id: UUID | None = Field(None, description="Existing systems_resource id when known")
    name: str = Field(..., description="System display name")
    description: str | None = Field(None, description="Optional description")
    agent_ids: list[UUID] = Field(default_factory=list, description="Agents that this system routes to")
    resolution_strategy: str | None = Field(None, description="Routing strategy, e.g. 'first', 'best', 'all'")
    resolution_threshold: float | None = Field(None, description="Score threshold (0–1) for resolution")


class SettingThresholdDraftValue(BaseModel):
    """Draft value object for a per-type threshold slider.

    Server resolver finds an existing thresholds_resource row matching
    (type, value) or creates one if none exists, then merges the id
    into request.threshold_ids (dropping any prior id of the same type
    so each type keeps exactly one assignment).
    """

    id: UUID | None = Field(None, description="Existing thresholds_resource id when known")
    type: str = Field(..., description="Threshold type — e.g. 'success', 'warning', 'danger'")
    value: int = Field(..., description="Integer threshold value (0–100)")


class SettingLoginOption(BaseModel):
    """Server-curated catalog option for the Logins picker."""

    login_type: str | None = Field(None, description="'auth' or 'profile'")
    auth_id: UUID | None = Field(None, description="Auth identifier for login_type='auth'")
    profile_id: UUID | None = Field(None, description="Profile identifier for login_type='profile'")
    display_name: str | None = Field(None, description="Default button label")
    icon_id: UUID | None = Field(None, description="Default icon (when Auth or Profile catalog provides one)")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (when available)")


class SettingLoginDraftValue(BaseModel):
    """Draft value object for an inline-creatable logins_resource row."""

    id: UUID | None = Field(None, description="Existing logins_resource id when known")
    login_type: str = Field(..., description="'auth' or 'profile'")
    auth_id: UUID | None = Field(None, description="Auth id — required when login_type='auth'")
    profile_id: UUID | None = Field(None, description="Profile id — required when login_type='profile'")
    display_name: str | None = Field(None, description="Override label; falls back to Auth/Profile catalog name")
    icon_id: UUID | None = Field(None, description="Override icon; falls back to defaults")


class SettingLoginsResource(BaseModel):
    logins_id: UUID | None = Field(None, description="Logins resource identifier")
    profile_id: UUID | None = Field(None, description="Profile for test login")
    auth_id: UUID | None = Field(None, description="Auth provider for OIDC login")
    icon_id: UUID | None = Field(None, description="Icon for login button")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    display_name: str | None = Field(None, description="Display text for login button")
    login_type: str | None = Field(None, description="Login type: 'auth' or 'profile'")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SettingProviderCatalogResource(BaseModel):
    id: UUID | None = Field(None, description="Provider identifier (canonical for picker selection)")
    provider_id: UUID | None = Field(None, description="Provider identifier (alias for id)")
    name: str | None = Field(None, description="Provider display name")
    description: str | None = Field(None, description="Provider description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


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
    logins: SectionFilter | None = Field(None, description="Filter options for logins")
    systems: SectionFilter | None = Field(None, description="Filter options for systems")
    mcp: SectionFilter | None = Field(None, description="Filter options for MCP configs")
    thresholds: SectionFilter | None = Field(None, description="Filter options for thresholds")
    provider_keys: SectionFilter | None = Field(None, description="Filter options for provider keys")
    auth_item_keys: SectionFilter | None = Field(None, description="Filter options for auth item keys")
    auth_item_values: SectionFilter | None = Field(None, description="Filter options for auth item values")


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
    flags: list[SettingFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    departments: list[SettingDepartmentResource] | None = Field(None, description="Department resources")
    logins: list[SettingLoginsResource] | None = Field(None, description="Logins resources")
    systems: list[SettingSystemResource] | None = Field(None, description="System resources")
    mcp: list[SettingMcpResource] | None = Field(None, description="MCP resources")
    thresholds: list[SettingThresholdResource] | None = Field(None, description="Threshold resources")
    provider_keys: list[SettingProviderKeyResource] | None = Field(None, description="Provider key resources")
    auth_item_keys: list[SettingAuthItemKeyResource] | None = Field(None, description="Auth item key resources")
    auth_item_values: list[SettingAuthItemValueResource] | None = Field(None, description="Auth item value resources")
    providers: list[SettingProviderCatalogResource] | None = Field(None, description="Provider catalog used by provider key editing")
    keys: list[SettingKeyCatalogResource] | None = Field(None, description="Key catalog used by provider key and auth item key editing")
    items: list[SettingItemCatalogResource] | None = Field(None, description="Claim item catalog used by auth item key/value editing")
    profiles: list[SettingProfileCatalogResource] | None = Field(None, description="Profile catalog used by logins editing")
    auths: list[SettingAuthCatalogResource] | None = Field(None, description="Auth catalog used by logins and auth item editing")
    icons: list[SettingIconCatalogResource] | None = Field(None, description="Icon catalog used by logins editing")
    agents: list[SettingAgentCatalogResource] | None = Field(None, description="Agent catalog used by mcp and systems editing")
    provider_key_options: list[SettingProviderKeyOption] | None = Field(None, description="Curated (provider × key) options for the ProviderKeys picker")
    auth_item_key_options: list[SettingAuthItemKeyOption] | None = Field(None, description="Curated (auth × key) options for the AuthItemKeys picker")
    auth_item_value_options: list[SettingAuthItemValueOption] | None = Field(None, description="Curated (auth × item) options for the AuthItemValues picker")
    mcp_options: list[SettingMcpOption] | None = Field(None, description="Curated per-agent options for the MCP picker")
    login_options: list[SettingLoginOption] | None = Field(None, description="Curated (auth × profile) options for the Logins picker")


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
    # Canonical flag state — ids of selected flag-resource rows. Server derives
    # semantics by flag type/value.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    # Legacy single-flag fields (deprecated — use `flag_ids`). Retained as
    # aliases so older callers (CSV import, seeded tools) keep working.
    active_flag_id: UUID | None = Field(None, description="DEPRECATED — use flag_ids. UUID of the active flag option")
    active_flag: bool | None = Field(None, description="DEPRECATED — use flag_ids. Whether the setting is active")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    color_ids: list[UUID] | None = Field(None, description="Color resource UUIDs")
    logins_ids: list[UUID] | None = Field(None, description="Logins resource UUIDs to assign")
    system_ids: list[UUID] | None = Field(None, description="System UUIDs to assign")
    mcp_id: UUID | None = Field(None, description="MCP resource UUID to assign (single)")
    threshold_ids: list[UUID] | None = Field(None, description="Threshold UUIDs to assign")
    provider_key_ids: list[UUID] | None = Field(None, description="Provider key UUIDs")
    auth_item_key_ids: list[UUID] | None = Field(None, description="Auth item key UUIDs")
    auth_item_value_ids: list[UUID] | None = Field(None, description="Auth item value UUIDs")
    auth_ids: list[UUID] | None = Field(None, description="Auth resource UUIDs to assign")
    provider_ids: list[UUID] | None = Field(None, description="Provider resource UUIDs to assign")
    setting_resource_ids: list[UUID] | None = Field(None, description="Setting resource UUIDs")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "flag_ids": "flags",
        "active_flag_id": "flags",
        "active_flag": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "color_ids": "colors",
        "logins_ids": "logins",
        "system_ids": "systems",
        "mcp_id": "mcp",
        "threshold_ids": "thresholds",
        "provider_key_ids": "provider_keys",
        "auth_item_key_ids": "auth_item_keys",
        "auth_item_value_ids": "auth_item_values",
        "auth_ids": "auths",
        "provider_ids": "providers",
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

    id: UUID = Field(..., description="UUID of the setting to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    # Canonical flag state — ids of selected flag-resource rows. Server derives
    # semantics by flag type/value.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    # Legacy single-flag fields (deprecated — use `flag_ids`). Retained as
    # aliases so older callers (CSV import, seeded tools) keep working.
    active_flag_id: UUID | None = Field(None, description="DEPRECATED — use flag_ids. UUID of the active flag option")
    active_flag: bool | None = Field(None, description="DEPRECATED — use flag_ids. Whether the setting is active")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    color_ids: list[UUID] | None = Field(None, description="Color resource UUIDs")
    logins_ids: list[UUID] | None = Field(None, description="Logins resource UUIDs to assign")
    system_ids: list[UUID] | None = Field(None, description="System UUIDs to assign")
    mcp_id: UUID | None = Field(None, description="MCP resource UUID to assign (single)")
    threshold_ids: list[UUID] | None = Field(None, description="Threshold UUIDs to assign")
    provider_key_ids: list[UUID] | None = Field(None, description="Provider key UUIDs")
    auth_item_key_ids: list[UUID] | None = Field(None, description="Auth item key UUIDs")
    auth_item_value_ids: list[UUID] | None = Field(None, description="Auth item value UUIDs")
    auth_ids: list[UUID] | None = Field(None, description="Auth resource UUIDs to assign")
    provider_ids: list[UUID] | None = Field(None, description="Provider resource UUIDs to assign")
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
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized setting_active flag state; resolved to a flag_ids entry server-side")
    mcp: bool | None = Field(None, description="Denormalized mcp flag state; resolved to a flag_ids entry server-side")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    color_ids: list[UUID] | None = Field(None, description="Color resource UUIDs")
    logins_ids: list[UUID] | None = Field(None, description="Logins resource UUIDs to assign")
    system_ids: list[UUID] | None = Field(None, description="System UUIDs to assign")
    mcp_id: UUID | None = Field(None, description="MCP resource UUID to assign (single)")
    threshold_ids: list[UUID] | None = Field(None, description="Threshold UUIDs to assign")
    provider_key_ids: list[UUID] | None = Field(None, description="Provider key UUIDs")
    auth_item_key_ids: list[UUID] | None = Field(None, description="Auth item key UUIDs")
    auth_item_value_ids: list[UUID] | None = Field(None, description="Auth item value UUIDs")
    auth_ids: list[UUID] | None = Field(None, description="Auth resource UUIDs to assign")
    provider_ids: list[UUID] | None = Field(None, description="Provider resource UUIDs to assign")
    provider_keys: list[SettingProviderKeyDraftValue] | None = Field(None, description="Inline-creatable (provider × key) value entries; id=null requests server to resolve or create")
    auth_item_keys: list[SettingAuthItemKeyDraftValue] | None = Field(None, description="Inline-creatable (auth × key) value entries")
    auth_item_values: list[SettingAuthItemValueDraftValue] | None = Field(None, description="Inline-creatable (auth × item × value) entries")
    mcp_values: list[SettingMcpDraftValue] | None = Field(None, description="Inline-creatable mcp value entries")
    system_values: list[SettingSystemDraftValue] | None = Field(None, description="Inline-creatable systems_resource value entries")
    threshold_values: list[SettingThresholdDraftValue] | None = Field(None, description="Per-type threshold slider values; server finds or creates a row per (type, value) and swaps the matching type into threshold_ids")
    logins: list[SettingLoginDraftValue] | None = Field(None, description="Inline-creatable logins_resource value entries (auth or profile buttons)")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to retain as pending inactive connections")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "departments": "departments",
        "department_ids": "departments",
        "color_ids": "colors",
        "logins_ids": "logins",
        "system_ids": "systems",
        "mcp_id": "mcp",
        "threshold_ids": "thresholds",
        "provider_key_ids": "provider_keys",
        "auth_item_key_ids": "auth_item_keys",
        "auth_item_value_ids": "auth_item_values",
        "auth_ids": "auths",
        "provider_ids": "providers",
    }


class DraftFormState(BaseModel):
    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    name: str | None = Field(None, description="Echoed name value when available")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    description: str | None = Field(None, description="Echoed description value when available")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed setting_active flag state")
    mcp: bool | None = Field(None, description="Echoed mcp flag state")
    department_ids: list[UUID] = Field(default_factory=list, description="Assigned department UUIDs")
    color_ids: list[UUID] = Field(default_factory=list, description="Assigned color UUIDs")
    logins_ids: list[UUID] = Field(default_factory=list, description="Assigned logins resource UUIDs")
    system_ids: list[UUID] = Field(default_factory=list, description="Assigned system UUIDs")
    mcp_id: UUID | None = Field(None, description="Assigned MCP resource UUID")
    threshold_ids: list[UUID] = Field(default_factory=list, description="Assigned threshold UUIDs")
    provider_key_ids: list[UUID] = Field(default_factory=list, description="Assigned provider key UUIDs")
    auth_item_key_ids: list[UUID] = Field(default_factory=list, description="Assigned auth item key UUIDs")
    auth_item_value_ids: list[UUID] = Field(default_factory=list, description="Assigned auth item value UUIDs")
    auth_ids: list[UUID] = Field(default_factory=list, description="Assigned auth resource UUIDs")
    provider_ids: list[UUID] = Field(default_factory=list, description="Assigned provider resource UUIDs")
    provider_keys: list[SettingProviderKeyDraftValue] = Field(default_factory=list, description="Echoed (provider × key) value entries with resolved ids")
    auth_item_keys: list[SettingAuthItemKeyDraftValue] = Field(default_factory=list, description="Echoed (auth × key) value entries with resolved ids")
    auth_item_values: list[SettingAuthItemValueDraftValue] = Field(default_factory=list, description="Echoed (auth × item × value) entries with resolved ids")
    mcp_values: list[SettingMcpDraftValue] = Field(default_factory=list, description="Echoed mcp value entries with resolved ids")
    system_values: list[SettingSystemDraftValue] = Field(default_factory=list, description="Echoed system value entries with resolved ids")
    threshold_values: list[SettingThresholdDraftValue] = Field(default_factory=list, description="Echoed per-type threshold values with resolved ids")
    logins: list[SettingLoginDraftValue] = Field(default_factory=list, description="Echoed logins value entries with resolved ids")
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
    is_inactive: bool | None = Field(None, description="Whether the setting is inactive")
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
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")


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
