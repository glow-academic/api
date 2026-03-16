"""Types for auth artifact — internal context + HTTP boundary types."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.auth.create import CreateAuthItem
from app.infra.identity.settings import SettingsThemeResult
from app.infra.shared_types import (
    QGetAgentsV4Item,
    QGetProfileContextV4ThemeTokens,
    QGetSettingsV4Item,
    QGetSystemsV4Item,
    QGetToolsV4Item,
)
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.auth_drafts.types import GetAuthDraftResponse


@dataclass
class SettingsAgentToolEntry:
    """Flat agent→tool entry resolved from settings chain.

    Exactly one of resource/entry/artifact is set per tool:
    - resource: tool creates/uses a *_resource row (e.g. "names", "personas")
    - entry: tool creates a *_entry row (e.g. "contents", "feedbacks")
    - artifact: tool reads an artifact (e.g. "attempt", "persona")
    """

    agent_id: UUID
    tool_id: UUID
    is_creatable: bool  # from tools_resource.operation == 'create'
    resource: str | None = None  # e.g. "names", "personas", "objectives"
    entry: str | None = None  # e.g. "contents", "hints", "feedbacks"
    artifact: str | None = None  # e.g. "attempt", "persona", "scenario"

    @property
    def type_name(self) -> str:
        """The effective type name — exactly one of resource/entry/artifact."""
        return self.resource or self.entry or self.artifact or ""


@dataclass
class AuthSettingsInternalData:
    """Hydrated settings — settings resource + agents + tools + theme."""

    settings_id: UUID | None
    settings: QGetSettingsV4Item | None
    settings_systems: list[QGetSystemsV4Item]
    settings_agents: list[QGetAgentsV4Item]
    settings_tools: list[QGetToolsV4Item]
    settings_theme: SettingsThemeResult | None
    settings_tokens: QGetProfileContextV4ThemeTokens
    artifact_has_generate: dict[str, bool]
    agent_tool_entries: list[SettingsAgentToolEntry]


class GetAuthSettingsApiResponse(BaseModel):
    """Response for POST /auth/settings — department-level settings + theme."""

    settings_id: str | None = Field(None, description="Active settings UUID")
    success_threshold: int | None = Field(None, description="Success score threshold")
    warning_threshold: int | None = Field(None, description="Warning score threshold")
    danger_threshold: int | None = Field(None, description="Danger score threshold")
    tokens: QGetProfileContextV4ThemeTokens | None = Field(None, description="Theme tokens for the client")
    systems: list[QGetSystemsV4Item] | None = Field(None, description="Available system configurations")
    agents: list[QGetAgentsV4Item] | None = Field(None, description="Available agent configurations")
    tools: list[QGetToolsV4Item] | None = Field(None, description="Available tool configurations")
    artifact_has_generate: dict[str, bool] | None = Field(None, description="Map of artifact type to AI generate availability")


# ---------------------------------------------------------------------------
# Resolve group_id types
# ---------------------------------------------------------------------------


class ResolveGroupApiRequest(BaseModel):
    """Request body for POST /auth/group — resolve or create a group_id."""

    draft_id: UUID | None = Field(None, description="Draft UUID to resolve group for")
    artifact_type: str | None = Field(None, description="Artifact type for group resolution")
    attempt_id: UUID | None = Field(None, description="Attempt UUID for simulation path")
    test_id: UUID | None = Field(None, description="Test UUID for benchmark path")


class ResolveGroupApiResponse(BaseModel):
    """Response for POST /auth/group — resolved group_id + optional attempt controls."""

    group_id: str = Field(..., description="Resolved group UUID")
    show_controls: bool = Field(False, description="Whether to show attempt/test controls")
    # Attempt controls (simulation path)
    attempt_id: str | None = Field(None, description="Attempt UUID for simulation")
    current_chat_id: str | None = Field(None, description="Current chat UUID for the attempt")
    has_messages: bool = Field(False, description="Whether the chat has existing messages")
    # Test controls (benchmark path)
    test_id: str | None = Field(None, description="Test UUID for benchmarking")
    current_invocation_id: str | None = Field(None, description="Current invocation UUID for the test")
    has_runs_or_groups: bool = Field(False, description="Whether the test has existing runs")


# ---------------------------------------------------------------------------
# Analytics filters types
# ---------------------------------------------------------------------------


class AnalyticsFilterField(BaseModel):
    """Visibility/disabled state for a single filter field."""

    visible: bool = Field(True, description="Whether the filter field is visible")
    disabled: bool = Field(False, description="Whether the filter field is disabled")


class AnalyticsFilterFields(BaseModel):
    """Per-page filter field visibility configuration."""

    date_range: AnalyticsFilterField = Field(default_factory=AnalyticsFilterField, description="Date range filter config")
    departments: AnalyticsFilterField = Field(default_factory=AnalyticsFilterField, description="Department filter config")
    cohorts: AnalyticsFilterField = Field(default_factory=AnalyticsFilterField, description="Cohort filter config")
    roles: AnalyticsFilterField = Field(default_factory=AnalyticsFilterField, description="Role filter config")
    attempts: AnalyticsFilterField = Field(default_factory=AnalyticsFilterField, description="Attempt filter config")


class AnalyticsFilterOption(BaseModel):
    """A single filter option for dropdown selectors."""

    value: str = Field(..., description="Option value for the filter")
    label: str = Field(..., description="Human-readable option label")


class AnalyticsFacets(BaseModel):
    """Resolved analytics facets — embeddable in any artifact response.

    Contains filter field visibility, available options for dropdowns,
    and date range boundaries. Returned inline from artifact get/search
    responses so each page has its filter facets ready for SSR.
    """

    fields: AnalyticsFilterFields = Field(..., description="Filter field visibility configuration")
    department_options: list[AnalyticsFilterOption] = Field(default_factory=list, description="Department dropdown options")
    cohort_options: list[AnalyticsFilterOption] = Field(default_factory=list, description="Cohort dropdown options")
    role_options: list[str] = Field(default_factory=list, description="Available role options")
    attempt_options: list[str] = Field(default_factory=list, description="Available attempt options")
    date_range_earliest: str | None = Field(None, description="Earliest available date for filtering")
    date_range_latest: str | None = Field(None, description="Latest available date for filtering")


class GetAnalyticsFiltersApiResponse(AnalyticsFacets):
    """Response for POST /auth/analytics (backward-compatible)."""

    pass


# ---------------------------------------------------------------------------
# Auth artifact HTTP boundary types
# ---------------------------------------------------------------------------


class AuthFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description text")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="UUID of the selected flag option")
    show: bool = Field(True, description="Whether the flag is visible to the client")
    required: bool = Field(False, description="Whether the flag is required")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")


class AuthItemResource(BaseModel):
    """Auth item resource shape for client/editing."""

    auth_item_id: UUID | None = Field(None, description="Unique auth item identifier")
    name: str | None = Field(None, description="Auth item display name")
    description: str | None = Field(None, description="Auth item description text")
    position: int | None = Field(None, description="Sort position within the auth provider")
    active: bool | None = Field(None, description="Whether the auth item is active")
    value_masked: str | None = Field(None, description="Masked value for display")
    key_id: UUID | None = Field(None, description="UUID of the associated key")
    encrypted: bool | None = Field(None, description="Whether the value is encrypted")
    generated: bool | None = Field(None, description="Whether the item was AI-generated")


class AuthNameSection(BaseResourceSection):
    resource: object | None = Field(None, description="Currently selected name resource")
    resources: list | None = Field(None, description="Available name resources")


class AuthDescriptionSection(BaseResourceSection):
    resource: object | None = Field(None, description="Currently selected description resource")
    resources: list | None = Field(None, description="Available description resources")


class AuthFlagSection(BaseResourceSection):
    current: list[AuthFlagConfig] | None = Field(None, description="Currently assigned flag configs")
    resources: list[AuthFlagConfig] | None = Field(None, description="Available flag configs")


class AuthProtocolSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned protocols")
    resources: list | None = Field(None, description="Available protocol resources")


class AuthSlugSection(BaseResourceSection):
    current: list | None = Field(None, description="Currently assigned slugs")
    resources: list | None = Field(None, description="Available slug resources")


class AuthItemSection(BaseResourceSection):
    current: list[AuthItemResource] | None = Field(None, description="Currently assigned auth items")
    resources: list[AuthItemResource] | None = Field(None, description="Available auth item resources")


class GetAuthApiRequest(BaseModel):
    """Request model for get auth endpoint."""

    auth_id: UUID | None = Field(None, description="UUID of the auth provider to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")


class GetAuthApiResponse(BaseModel):
    """Response model for get auth endpoint."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    auth_exists: bool | None = Field(None, description="Whether the auth provider exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this auth")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")

    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate button")

    names: AuthNameSection | None = Field(None, description="Name section with resources")
    descriptions: AuthDescriptionSection | None = Field(None, description="Description section with resources")
    flags: AuthFlagSection | None = Field(None, description="Flag section with configs")
    protocols: AuthProtocolSection | None = Field(None, description="Protocol section with resources")
    slugs: AuthSlugSection | None = Field(None, description="Slug section with resources")
    items: AuthItemSection | None = Field(None, description="Auth item section with resources")


class GetAuthDraftsApiResponse(BaseModel):
    """Response model for auth drafts list endpoint."""

    entries: list[GetAuthDraftResponse] | None = Field(None, description="List of auth draft entries")


# ========== Shared Create/Update Types ==========


class AuthFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class AuthResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    auth_id: UUID | None = Field(None, description="UUID of the created or updated auth")
    message: str = Field(..., description="Result message")
    errors: list[AuthFieldError] | None = Field(None, description="Per-field validation errors")


# ========== Create Endpoint Types ==========


class CreateAuthApiRequest(BaseModel):
    """Request model for bulk create auth endpoint."""

    auths: list[CreateAuthItem] = Field(..., description="List of auth providers to create")


class CreateAuthApiResponse(BaseModel):
    """Response model for bulk create auth endpoint."""

    results: list[AuthResultItem] = Field(..., description="Per-item creation results")


# ========== Update Endpoint Types ==========


class UpdateAuthItem(BaseModel):
    """Single auth item for update — auth_id required, all fields optional."""

    auth_id: UUID = Field(..., description="UUID of the auth provider to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description value to resolve or create")
    slug_id: UUID | None = Field(None, description="UUID of the slug resource")
    slug: str | None = Field(None, description="Slug value to resolve or create")
    # Optional flag
    active_flag_id: UUID | None = Field(None, description="UUID of the active flag option")
    active_flag: bool | None = Field(None, description="Whether the auth provider is active")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    protocol_ids: list[UUID] | None = Field(None, description="Protocol resource UUIDs")
    protocol: str | None = Field(None, description="Protocol value to resolve")
    item_ids: list[UUID] | None = Field(None, description="Auth item UUIDs")
    auth_resource_ids: list[UUID] | None = Field(None, description="Auth resource UUIDs")


class UpdateAuthApiRequest(BaseModel):
    """Request model for bulk update auth endpoint."""

    auths: list[UpdateAuthItem] = Field(..., description="List of auth providers to update")


class UpdateAuthApiResponse(BaseModel):
    """Response model for bulk update auth endpoint."""

    results: list[AuthResultItem] = Field(..., description="Per-item update results")


class SaveAuthFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class DeleteAuthApiRequest(BaseModel):
    """Request model for bulk delete auth endpoint."""

    auth_ids: list[UUID] = Field(..., description="UUIDs of auth providers to delete")


class DeleteAuthResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    auth_id: UUID = Field(..., description="UUID of the deleted auth provider")
    message: str = Field(..., description="Result message")


class DeleteAuthApiResponse(BaseModel):
    """Response model for bulk delete auth endpoint."""

    results: list[DeleteAuthResult] = Field(..., description="Per-item deletion results")


class DuplicateAuthApiRequest(BaseModel):
    """Request model for duplicate auth endpoint."""

    auth_id: UUID = Field(..., description="UUID of the auth provider to duplicate")


class DuplicateAuthApiResponse(BaseModel):
    """Response model for duplicate auth endpoint."""

    success: bool = Field(..., description="Whether the duplication succeeded")
    auth_id: UUID = Field(..., description="UUID of the newly created auth provider")
    message: str = Field(..., description="Result message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchAuthDraftApiRequest(BaseModel):
    """Request model for new-style auth draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_id, department_ids, protocol_ids, slug_ids, item_ids

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
    protocol_ids: list[UUID] | None = Field(None, description="Protocol resource UUIDs")
    slug_ids: list[UUID] | None = Field(None, description="Slug resource UUIDs")
    item_ids: list[UUID] | None = Field(None, description="Auth item UUIDs")


class AuthDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    flag_id: UUID | None = Field(None, description="Resolved flag option UUID")
    department_ids: list[UUID] = Field(..., description="Assigned department UUIDs")
    protocol_ids: list[UUID] = Field(..., description="Assigned protocol UUIDs")
    slug_ids: list[UUID] = Field(..., description="Assigned slug UUIDs")
    item_ids: list[UUID] = Field(..., description="Assigned auth item UUIDs")


class PatchAuthDraftApiResponse(BaseModel):
    """Response model for new-style auth draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Result message")
    form_state: AuthDraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Export Endpoint Types ==========


class ExportAuthApiRequest(BaseModel):
    """Request model for auth export."""

    auth_id: UUID | None = Field(None, description="UUID of the auth provider to export")


class ExportAuthApiResponse(BaseModel):
    """Response model for export auth endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


class ListAuthApiAuth(BaseModel):
    """Auth type for list endpoint with computed permissions."""

    auth_id: UUID | None = Field(None, description="Unique auth provider identifier")
    name: str | None = Field(None, description="Auth provider display name")
    description: str | None = Field(None, description="Auth provider description text")
    item_count: int | None = Field(None, description="Number of auth items")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    is_inactive: bool | None = Field(None, description="Whether the auth provider is inactive")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this auth")
    can_duplicate: bool | None = Field(None, description="Whether the actor can duplicate this auth")
    can_delete: bool | None = Field(None, description="Whether the actor can delete this auth")


class ListAuthApiResponse(BaseModel):
    """Response model for list auth endpoint with computed permissions."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    auths: list[ListAuthApiAuth] | None = Field(None, description="List of auth provider items")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments")
    total_count: int | None = Field(None, description="Total number of auth providers")
