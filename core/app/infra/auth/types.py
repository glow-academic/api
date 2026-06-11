"""Types for auth artifact — internal context + HTTP boundary types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.identity.settings import SettingsThemeResult
from app.infra.resource_type_filter import ScopedItem
from app.infra.shared_types import (
    MAX_BULK_ITEMS,
    MAX_TEXT_FIELD_LEN,
    QGetAgentsV4Item,
    QGetProfileContextV4ThemeTokens,
    QGetSettingsV4Item,
    QGetSystemsV4Item,
    QGetToolsV4Item,
)
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


class AnalyticsRoleOption(AnalyticsFilterOption):
    """Hydrated role resource option for analytics role filters."""

    id: str = Field(..., description="Role resource UUID")
    name: str = Field(..., description="Role resource name")
    description: str | None = Field(None, description="Role description")
    icon_id: str | None = Field(None, description="Icon resource UUID")
    color_id: str | None = Field(None, description="Color resource UUID")
    level: int = Field(..., description="Role privilege level")


class AnalyticsFacets(BaseModel):
    """Resolved analytics facets — embeddable in any artifact response.

    Contains filter field visibility, available options for dropdowns,
    and date range boundaries. Returned inline from artifact get/search
    responses so each page has its filter facets ready for SSR.
    """

    fields: AnalyticsFilterFields = Field(..., description="Filter field visibility configuration")
    department_options: list[AnalyticsFilterOption] = Field(default_factory=list, description="Department dropdown options")
    cohort_options: list[AnalyticsFilterOption] = Field(default_factory=list, description="Cohort dropdown options")
    role_options: list[AnalyticsRoleOption] = Field(default_factory=list, description="Available role resource options")
    attempt_options: list[str] = Field(default_factory=list, description="Available attempt options")
    date_range_earliest: str | None = Field(None, description="Earliest available date for filtering")
    date_range_latest: str | None = Field(None, description="Latest available date for filtering")


class GetAnalyticsFiltersApiResponse(AnalyticsFacets):
    """Response for POST /auth/analytics (backward-compatible)."""

    pass


# ---------------------------------------------------------------------------
# Auth artifact HTTP boundary types
# ---------------------------------------------------------------------------


class AuthNameResource(BaseModel):
    """Name resource for auth."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class AuthDescriptionResource(BaseModel):
    """Description resource for auth."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class AuthDepartmentResource(BaseModel):
    """Department resource for auth."""

    department_id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class AuthFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'auth_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class AuthProtocolResource(BaseModel):
    """Protocol resource for auth."""

    id: UUID | None = Field(None, description="Protocol identifier")
    value: str | None = Field(None, description="Protocol value")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class AuthSlugResource(BaseModel):
    """Slug resource for auth."""

    id: UUID | None = Field(None, description="Slug identifier")
    value: str | None = Field(None, description="Slug value")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class AuthItemResource(BaseModel):
    """Auth item resource shape for client/editing."""

    id: UUID | None = Field(None, description="Unique auth item identifier")
    name: str | None = Field(None, description="Auth item display name")
    description: str | None = Field(None, description="Auth item description text")
    position: int | None = Field(None, description="Sort position within the auth provider")
    encrypted: bool | None = Field(None, description="Whether the value is encrypted")
    generated: bool | None = Field(None, description="Whether the item was AI-generated")
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
    parameter_ids: list[str] | None = Field(None, description="Unused for auth; present for shared request compatibility")


class GetAuthApiRequest(BaseModel):
    """Request model for get auth endpoint."""

    id: UUID | None = Field(None, description="Auth identifier")
    auth_id: UUID | None = Field(None, description="Legacy alias for auth identifier")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    protocols: SectionFilter | None = Field(None, description="Filter options for protocols section")
    slugs: SectionFilter | None = Field(None, description="Filter options for slugs section")
    items: SectionFilter | None = Field(None, description="Filter options for items section")


class GetAuthApiResponse(BaseModel):
    """Canonical flat composed response for the auth editor."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    auth_exists: bool | None = Field(None, description="Whether the auth provider exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this auth")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    show_ai_generate: bool | None = Field(None, description="Whether any auth resource supports AI generate")
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate button")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    names: list[AuthNameResource] | None = Field(None, description="Name resources")
    descriptions: list[AuthDescriptionResource] | None = Field(None, description="Description resources")
    flags: list[AuthFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    departments: list[AuthDepartmentResource] | None = Field(None, description="Department resources")
    protocols: list[AuthProtocolResource] | None = Field(None, description="Protocol resources")
    slugs: list[AuthSlugResource] | None = Field(None, description="Slug resources")
    items: list[AuthItemResource] | None = Field(None, description="Auth item resources")


class GetAuthDraftsApiRequest(BaseModel):
    """Request model for the auth drafts list endpoint.

    Mirrors ``GenerationsAuthApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


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


class CreateAuthItem(ScopedItem):
    """Single auth item for create — no auth_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "slug_id": "slugs",
        "slug": "slugs",
        "flag_ids": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "protocol_ids": "protocols",
        "protocol": "protocols",
        "item_ids": "items",
        "auth_resource_ids": "auths",
    }

    id: UUID | None = Field(None, description="Optional preset UUID for the new auth provider")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required pairs (one of each pair must be set on create) — see
    # ``permissions_context.py::resolve_auth_values`` for the runtime
    # check. Descriptions flag this so the OpenAPI schema consumed by
    # LLM tool callers makes the constraint explicit.
    name_id: UUID | None = Field(
        None,
        description="REQUIRED FOR CREATE (or pass ``name``). UUID of an existing name resource.",
    )
    name: str | None = Field(
        None,
        max_length=MAX_TEXT_FIELD_LEN,
        description="REQUIRED FOR CREATE (or pass ``name_id``). Display name text — creates a new name resource on the fly.",
    )
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Description value to resolve or create")
    slug_id: UUID | None = Field(None, description="UUID of the slug resource")
    slug: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Slug value to resolve or create")
    # Canonical flag ids + denormalized bool
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Denormalized auth_active flag state")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    protocol_ids: list[UUID] | None = Field(None, description="Protocol resource UUIDs")
    protocol: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Protocol value to resolve")
    item_ids: list[UUID] | None = Field(None, description="Auth item UUIDs")
    auth_resource_ids: list[UUID] | None = Field(None, description="Auth resource UUIDs")


class CreateAuthApiRequest(BaseModel):
    """Request model for bulk create auth endpoint.

    Two body shapes:
      - First call: ``auths`` required.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant artifact by ``idempotency_key``.
    """

    auths: list[CreateAuthItem] | None = Field(
        None, max_length=MAX_BULK_ITEMS, description="List of auth providers to create (required on first call)",
    )
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    soft: bool = Field(False, description="Stage the create dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateAuthApiResponse(BaseModel):
    """Response model for bulk create auth endpoint."""

    results: list[AuthResultItem] = Field(..., description="Per-item creation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # Full row content for each successfully-created auth — same shape
    # ``/auth/search`` returns. The audit framework spreads response
    # fields into the wire payload, so the client's ghost rail can
    # materialize the new row directly from ``auth.create.completed``
    # without an SSR refresh round-trip.
    auths: list["ListAuthApiAuth"] | None = Field(
        None, description="Hydrated rows for the successfully-created auths (mirrors /auth/search shape)",
    )


# ========== Update Endpoint Types ==========


class UpdateAuthItem(ScopedItem):
    """Single auth item for update — auth_id required, all fields optional."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateAuthItem.RESOURCE_TYPE_MAP

    id: UUID = Field(..., description="UUID of the auth provider to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Name value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Description value to resolve or create")
    slug_id: UUID | None = Field(None, description="UUID of the slug resource")
    slug: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Slug value to resolve or create")
    # Canonical flag ids + denormalized bool
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Denormalized auth_active flag state")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    protocol_ids: list[UUID] | None = Field(None, description="Protocol resource UUIDs")
    protocol: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Protocol value to resolve")
    item_ids: list[UUID] | None = Field(None, description="Auth item UUIDs")
    auth_resource_ids: list[UUID] | None = Field(None, description="Auth resource UUIDs")


class UpdateAuthPatch(UpdateAuthItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateAuthItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved auth id per matched row",
    )


class UpdateAuthApiRequest(BaseModel):
    """Request model for bulk update auth endpoint.

    Three body shapes:
      - First call (explicit): ``auths`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/auth/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    auths: list[UpdateAuthItem] | None = Field(
        None, description="List of auth providers to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteAuthApiRequest; ``patch``
    # is the shared change set applied to every matched row. ``patch.id``
    # is ignored — each resolved id is stamped onto a clone before the
    # per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every auth matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateAuthPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    soft: bool = Field(False, description="Stage the update dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateAuthApiResponse(BaseModel):
    """Response model for bulk update auth endpoint."""

    results: list[AuthResultItem] = Field(..., description="Per-item update results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # See CreateAuthApiResponse.auths — same role here for updates.
    auths: list["ListAuthApiAuth"] | None = Field(
        None, description="Hydrated rows for the successfully-updated auths (mirrors /auth/search shape)",
    )


class SaveAuthFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class DeleteAuthApiRequest(BaseModel):
    """Request model for bulk delete auth endpoint.

    Three body shapes:
      - First call (explicit): ``auth_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/auth/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    auth_ids: list[UUID] | None = Field(
        None, description="UUIDs of auth providers to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchAuthApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every auth matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /auth/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``auth_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    soft: bool = Field(False, description="Stage the delete dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteAuthResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    # Relaxed to ``UUID | None`` so soft-skipped rows (under all-matching)
    # whose ids didn't resolve to an actual artifact can still be
    # reported. Explicit-ids path always populates this.
    auth_id: UUID | None = Field(None, description="UUID of the deleted auth provider")
    message: str = Field(..., description="Result message")


class DeleteAuthApiResponse(BaseModel):
    """Response model for bulk delete auth endpoint."""

    results: list[DeleteAuthResult] = Field(..., description="Per-item deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateAuthApiRequest(BaseModel):
    """Request model for duplicate auth endpoint."""

    auth_id: UUID = Field(..., description="UUID of the auth provider to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    soft: bool = Field(False, description="Stage the duplicate dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateAuthApiResponse(BaseModel):
    """Response model for duplicate auth endpoint."""

    success: bool = Field(..., description="Whether the duplication succeeded")
    auth_id: UUID = Field(..., description="UUID of the newly created auth provider")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # See CreateAuthApiResponse.auths — single-element list here
    # (duplicate creates exactly one row), but kept as a list for shape
    # consistency across create/duplicate/update on the wire.
    auths: list["ListAuthApiAuth"] | None = Field(
        None, description="Hydrated row for the newly-created duplicate auth (mirrors /auth/search shape)",
    )


# ========== Draft Endpoint Types (composable infra) ==========


class PatchAuthDraftApiRequest(ScopedItem):
    """Request model for new-style auth draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_id, department_ids, protocol_ids, slug_ids, item_ids

    Client always sends full state (append-only — each write is a new snapshot).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "departments": "departments",
        "department_ids": "departments",
        "protocols": "protocols",
        "protocol_ids": "protocols",
        "slugs": "slugs",
        "slug_ids": "slugs",
        "item_ids": "items",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    idempotency_key: UUID | None = Field(None, description="Stable idempotency key for ack/promote flows")
    soft: bool = Field(False, description="Stage the draft dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Whether to accept a pending draft when acknowledging")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Name value to resolve or create")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Description value to resolve or create")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    # Canonical flag ids + denormalized bools resolved server-side
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized auth_active flag state; resolved to a flag_ids entry server-side")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    protocols: list[str] | None = Field(None, description="Protocol values to resolve")
    protocol_ids: list[UUID] | None = Field(None, description="Protocol resource UUIDs")
    slugs: list[str] | None = Field(None, description="Slug values to resolve")
    slug_ids: list[UUID] | None = Field(None, description="Slug resource UUIDs")
    item_ids: list[UUID] | None = Field(None, description="Auth item UUIDs")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep pending where supported")

class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name: str | None = Field(None, description="Echoed name value")
    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    description: str | None = Field(None, description="Echoed description value")
    description_id: UUID | None = Field(None, description="Resolved description resource UUID")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed auth_active flag state")
    department_ids: list[UUID] = Field(default_factory=list, description="Assigned department UUIDs")
    protocol_ids: list[UUID] = Field(default_factory=list, description="Assigned protocol UUIDs")
    slug_ids: list[UUID] = Field(default_factory=list, description="Assigned slug UUIDs")
    item_ids: list[UUID] = Field(default_factory=list, description="Assigned auth item UUIDs")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


AuthDraftFormState = DraftFormState


class PatchAuthDraftApiResponse(BaseModel):
    """Response model for new-style auth draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    idempotency_key: UUID | None = Field(None, description="Stable idempotency key for ack/promote flows")
    message: str = Field(..., description="Result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== Export Endpoint Types ==========


class ExportAuthApiRequest(BaseModel):
    """Request model for auth export."""

    auth_id: UUID | None = Field(None, description="UUID of the auth provider to export")
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")


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
    setting_ids: list[UUID] = Field(default_factory=list, description="Setting artifact UUIDs that reference this auth")
    auth_item_key_ids: list[UUID] = Field(default_factory=list, description="Auth item key resource UUIDs owned by this auth")
    is_inactive: bool | None = Field(None, description="Whether the auth provider is inactive")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this auth")
    can_duplicate: bool | None = Field(None, description="Whether the actor can duplicate this auth")
    can_delete: bool | None = Field(None, description="Whether the actor can delete this auth")
    pending_status: str | None = Field(None, description="Soft-call ledger status (pending/accepted/rejected) for the latest pending op on this row")
    pending_operation: str | None = Field(None, description="Operation name (create/update/delete/duplicate/draft) of the latest pending soft-call entry")
    pending_call_id: UUID | None = Field(None, description="Originating tool call id for the latest pending soft-call entry")


class ListAuthApiResponse(BaseModel):
    """Response model for list auth endpoint with computed permissions."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    auths: list[ListAuthApiAuth] | None = Field(None, description="List of auth provider items")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments")
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
    settings_filter: ListFilterSection | None = Field(None, description="Filter options for settings in list UI")
    auth_item_keys_filter: ListFilterSection | None = Field(None, description="Filter options for auth item keys in list UI")
    total_count: int | None = Field(None, description="Total number of auth providers")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsAuthApiRequest(BaseModel):
    """Request model for auth generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GenerationsAuthListItem(BaseModel):
    """Single generation group in the auth generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsAuthApiResponse(BaseModel):
    """Response model for auth generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsAuthListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemAuthApiRequest(BaseModel):
    """Request model for auth problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemAuthApiResponse(BaseModel):
    """Response model for auth problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadAuthApiRequest(BaseModel):
    """Request model for auth text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadAuthApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadAuthApiRequest(BaseModel):
    """Request model for auth call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadAuthApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


class FileDownloadAuthApiRequest(BaseModel):
    """Request model for auth file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadAuthApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
