"""Handcrafted types for profile artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.resource_type_filter import ScopedItem
from app.infra.shared_types import (
    MAX_BULK_ITEMS,
    MAX_TEXT_FIELD_LEN,
    QGetProfileContextV4RoleResource,
)
from app.tools.entries.profile_drafts.types import GetProfileDraftResponse
from app.utils.settings.theme import ThemeTokens

# ---------------------------------------------------------------------------
# Handcrafted resource types (replaces Q types from app.sql.types)
# ---------------------------------------------------------------------------


class ProfileNameResource(BaseModel):
    """Name resource for profile."""

    id: UUID | None = Field(None, description="Unique resource identifier")
    name: str | None = Field(None, description="Profile display name")
    generated: bool | None = Field(None, description="Whether the name was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class ProfileEmailResource(BaseModel):
    """Email resource for profile."""

    id: UUID | None = Field(None, description="Unique resource identifier")
    email: str | None = Field(None, description="Email address")
    is_primary: bool = Field(False, description="Whether this is the profile's primary email")
    generated: bool | None = Field(None, description="Whether the email was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class ProfileDepartmentResource(BaseModel):
    """Department resource for profile."""

    department_id: UUID | None = Field(None, description="Unique resource identifier")
    name: str | None = Field(None, description="Department display name")
    description: str | None = Field(None, description="Department description text")
    generated: bool | None = Field(None, description="Whether the resource was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class ProfileRoleResource(BaseModel):
    """Role resource for profile."""

    id: UUID | None = Field(None, description="Unique resource identifier")
    role: str | None = Field(None, description="Role key (e.g. admin, user, viewer)")
    name: str | None = Field(None, description="Role display name")
    description: str | None = Field(None, description="Role description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the role")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    icon_value: str | None = Field(None, description="Legacy alias for resolved role icon SVG")
    color_id: UUID | None = Field(None, description="Color identifier for the role")
    color_hex: str | None = Field(None, description="Resolved role color hex code")
    level: int | None = Field(None, description="Role level for assignment filtering")
    permission_ids: list[UUID] = Field(default_factory=list, description="Permission resource UUIDs attached to this role")
    request_limit_ids: list[UUID] = Field(default_factory=list, description="Request limit resource UUIDs attached to this role")
    generated: bool | None = Field(None, description="Whether the role was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class ProfilePermissionResource(BaseModel):
    """Permission catalog row — one per (artifact, operation) pair."""

    id: UUID | None = Field(None, description="Permission resource identifier")
    artifact: str | None = Field(None, description="Artifact key (e.g. 'agent', 'profile')")
    operation: str | None = Field(None, description="Operation key (e.g. 'create', 'update')")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Description text")


class ProfileRequestLimitResource(BaseModel):
    """Request-limit catalog/echo row."""

    id: UUID | None = Field(None, description="Request limit resource identifier")
    limit: int | None = Field(None, description="Maximum number of requests per interval")
    interval: str | None = Field(None, description="Postgres interval string (e.g. '1 day', '30 minutes')")


class ProfileRequestLimitDraftValue(BaseModel):
    """Draft value for an inline-creatable request limit (limit, interval).

    id=null asks the server to create a new request_limits_resource row.
    id present means the caller is re-linking an existing limit.
    """

    id: UUID | None = Field(None, description="Existing request_limits_resource id when known")
    limit: int = Field(..., description="Maximum requests per interval")
    interval: str = Field(..., description="Postgres interval string (e.g. '1 day', '30 minutes', '2 hours')")


class ProfileRoleDraftValue(BaseModel):
    """Draft value for an inline-creatable role.

    Roles are immutable on this surface — the user can either re-link an
    existing role (id present) or create a new one (id=null + name + …).
    Nested request_limits with id=null are inline-created first; their
    resolved ids merge into request_limit_ids before role creation.
    """

    id: UUID | None = Field(None, description="Existing roles_resource id when re-linking")
    name: str | None = Field(None, description="Role name (required when creating)")
    description: str | None = Field(None, description="Role description")
    icon_id: UUID | None = Field(None, description="Icon resource identifier")
    color_id: UUID | None = Field(None, description="Color resource identifier")
    level: int = Field(99, description="Role level for assignment filtering")
    permission_ids: list[UUID] = Field(default_factory=list, description="Permission resource UUIDs to attach")
    request_limit_ids: list[UUID] = Field(default_factory=list, description="Existing request_limits_resource ids")
    request_limits: list[ProfileRequestLimitDraftValue] = Field(default_factory=list, description="Inline-creatable request limits; id=null entries are created server-side")


class ProfileFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'profile_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class ProfileDraftEntry(BaseModel):
    """Draft entry for profile."""

    id: UUID | None = Field(None, description="Unique draft identifier")

    created_at: datetime | None = Field(None, description="Timestamp when draft was created")
    generated: bool | None = Field(None, description="Whether the draft was AI-generated")
    mcp: bool | None = Field(None, description="Whether the draft was created via MCP")
    active: bool | None = Field(None, description="Whether the draft is active")
    group_id: UUID | None = Field(None, description="Group UUID for collaboration")
    session_id: UUID | None = Field(None, description="Session UUID of the creator")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs in the draft")
    email_ids: list[UUID] | None = Field(None, description="Email resource UUIDs in the draft")
    flag_ids: list[UUID] | None = Field(None, description="Flag option UUIDs in the draft")
    name_ids: list[UUID] | None = Field(None, description="Name resource UUIDs in the draft")
    role_ids: list[UUID] | None = Field(None, description="Role resource UUIDs in the draft")
    primary_department_ids: list[UUID] | None = Field(None, description="Primary-department resource UUIDs in the draft")


class SectionFilter(BaseModel):
    """Per-section filter options for GET requests."""

    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")


# ---------------------------------------------------------------------------
# GET endpoint types
# ---------------------------------------------------------------------------


class GetProfileApiRequest(BaseModel):
    id: UUID | None = Field(None, description="UUID of the profile to retrieve")
    target_profile_id: UUID | None = Field(None, description="Legacy alias for profile UUID")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    emails: SectionFilter | None = Field(None, description="Filter options for emails section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    roles: SectionFilter | None = Field(None, description="Filter options for roles section")


class GetProfileApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the acting user")
    profile_exists: bool | None = Field(None, description="Whether the profile exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this profile")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    profile_id: UUID | None = Field(None, description="UUID of the profile")
    show_ai_generate: bool | None = Field(None, description="Whether to show AI generate anywhere")
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate on the basic step")
    contact_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate on the contact step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")
    role_options: list[str] | None = Field(None, description="Role names the actor can assign")

    names: list[ProfileNameResource] | None = Field(None, description="Name resources")
    emails: list[ProfileEmailResource] | None = Field(None, description="Email resources")
    flags: list[ProfileFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    departments: list[ProfileDepartmentResource] | None = Field(None, description="Department resources")
    roles: list[ProfileRoleResource] | None = Field(None, description="Role resources")
    permissions: list[ProfilePermissionResource] | None = Field(None, description="Permission catalog for the role editor")
    request_limits: list[ProfileRequestLimitResource] | None = Field(None, description="Request-limit catalog for the role editor")


class GetProfileDraftsApiRequest(BaseModel):
    """Request model for the profile drafts list endpoint.

    Mirrors ``GenerationsProfileApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GetProfileDraftsApiResponse(BaseModel):
    """Response model for profile drafts list endpoint."""

    entries: list[GetProfileDraftResponse] | None = Field(None, description="List of profile draft entries")


# ========== Shared Create/Update Types ==========


class ProfileFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class ProfileResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    profile_id: UUID | None = Field(None, description="UUID of the created or updated profile")
    message: str = Field(..., description="Result message")
    errors: list[ProfileFieldError] | None = Field(None, description="Per-field validation errors")


# ========== Create Endpoint Types ==========


class CreateProfileItem(ScopedItem):
    """Single profile item for create — no profile_id."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "flag_ids": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "email_ids": "emails",
        "role_id": "roles",
        "primary_department_id": "departments",
    }

    id: UUID | None = Field(None, description="Optional preset UUID for the new profile")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required pair (one of the pair must be set on create) — see
    # ``permissions_context.py::resolve_profile_values`` for the runtime
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
    # Canonical flag ids + denormalized bool
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Denormalized profile_active flag state")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    email_ids: list[UUID] | None = Field(None, description="Email resource UUIDs")
    role_id: UUID | None = Field(None, description="Role resource UUID")
    # Single-select primary department — points into departments_resource
    primary_department_id: UUID | None = Field(None, description="UUID of the department to designate as primary")


class CreateProfileApiRequest(BaseModel):
    """Request model for bulk create profile endpoint."""

    profiles: list[CreateProfileItem] = Field(..., max_length=MAX_BULK_ITEMS, description="List of profiles to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    soft: bool = Field(False, description="Stage the create dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateProfileApiResponse(BaseModel):
    """Response model for bulk create profile endpoint."""

    results: list[ProfileResultItem] = Field(..., description="Per-item creation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # Full row content for each successfully-created profile — same shape
    # `/profile/search` returns. The audit framework spreads response
    # fields into the wire payload, so the client's ghost rail can
    # materialize the new row directly from `profile.create.completed`
    # without an SSR refresh round-trip.
    profiles: list[ListProfilesApiProfile] | None = Field(
        None,
        description="Hydrated rows for the successfully-created profiles (mirrors /profile/search shape)",
    )


# ========== Update Endpoint Types ==========


class UpdateProfileItem(ScopedItem):
    """Single profile item for update — profile_id required, all fields optional."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateProfileItem.RESOURCE_TYPE_MAP

    profile_id: UUID = Field(..., description="UUID of the profile to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Name value to resolve or create")
    # Canonical flag ids + denormalized bool
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Denormalized profile_active flag state")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    email_ids: list[UUID] | None = Field(None, description="Email resource UUIDs")
    role_id: UUID | None = Field(None, description="Role resource UUID")
    primary_department_id: UUID | None = Field(None, description="UUID of the department to designate as primary")


class UpdateProfilePatch(UpdateProfileItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateProfileItem`` and just relaxes
    ``profile_id`` to optional — the bulk impl stamps the resolved id
    onto a clone of the patch per matched row, so any client-supplied
    id is ignored. Sparse semantics: only fields the client sets are
    written.
    """

    profile_id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved profile id per matched row",
    )


class UpdateProfileApiRequest(BaseModel):
    """Request model for bulk update profile endpoint.

    Three body shapes:
      - First call (explicit): ``profiles`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/profile/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    profiles: list[UpdateProfileItem] | None = Field(
        None, description="List of profiles to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteProfileApiRequest; ``patch``
    # is the shared change set applied to every matched row.
    # ``patch.profile_id`` is ignored — each resolved id is stamped onto
    # a clone before the per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every profile matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateProfilePatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.profile_id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    cohort_ids: list[UUID] | None = Field(None, description="Filter by cohort UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    role_filter: str | None = Field(None, description="Filter by role name")
    cohort_search: str | None = Field(None, description="Search text for cohort facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    role_search: str | None = Field(None, description="Search text for role facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    soft: bool = Field(False, description="Stage the update dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateProfileApiResponse(BaseModel):
    """Response model for bulk update profile endpoint."""

    results: list[ProfileResultItem] = Field(..., description="Per-item update results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # See ``CreateProfileApiResponse.profiles`` — same role here for updates.
    profiles: list[ListProfilesApiProfile] | None = Field(
        None,
        description="Hydrated rows for the successfully-updated profiles (mirrors /profile/search shape)",
    )


class SaveProfileFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class DeleteProfileApiRequest(BaseModel):
    """Request model for bulk delete profile endpoint.

    Three body shapes:
      - First call (explicit): ``profile_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/profile/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    profile_ids: list[UUID] | None = Field(
        None, description="UUIDs of profiles to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchProfileApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every profile matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /profile/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``profile_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    cohort_ids: list[UUID] | None = Field(None, description="Filter by cohort UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    role_filter: str | None = Field(None, description="Filter by role name")
    cohort_search: str | None = Field(None, description="Search text for cohort facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    role_search: str | None = Field(None, description="Search text for role facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    soft: bool = Field(False, description="Stage the delete dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteProfileResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    # Relaxed to ``UUID | None`` so soft-skipped rows (not-found / no
    # permission under all-matching mode) can be reported with the
    # input id; explicit-ids path still always populates this.
    profile_id: UUID | None = Field(None, description="UUID of the deleted profile (None if soft-skipped under all-matching mode)")
    message: str = Field(..., description="Result message")


class DeleteProfileApiResponse(BaseModel):
    """Response model for bulk delete profile endpoint."""

    results: list[DeleteProfileResult] = Field(..., description="Per-item deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateProfileApiRequest(BaseModel):
    target_profile_id: UUID = Field(..., description="UUID of the profile to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    soft: bool = Field(False, description="Stage the duplicate dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateProfileApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    profile_id: UUID = Field(..., description="UUID of the newly created profile")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    # See ``CreateProfileApiResponse.profiles`` — single-element list here
    # (duplicate creates exactly one row), but kept as a list for shape
    # consistency across create/duplicate/update on the wire.
    profiles: list[ListProfilesApiProfile] | None = Field(
        None,
        description="Hydrated row for the newly-created duplicate profile (mirrors /profile/search shape)",
    )


# ========== Draft Endpoint Types (composable infra) ==========


class PatchProfileDraftApiRequest(ScopedItem):
    """Request model for new-style profile draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id
    ID-only for non-creatable resources:
      - flag_ids, department_ids, email_ids, role_id

    Client always sends full state (append-only — each write is a new snapshot).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "email": "emails",
        "emails": "emails",
        "flag_ids": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "email_ids": "emails",
        "role": "roles",
        "role_id": "roles",
        "primary_department_id": "departments",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to update")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, max_length=MAX_TEXT_FIELD_LEN, description="Name value to resolve or create")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    email: str | None = Field(None, description="Email value to resolve or create")
    emails: list[str] | None = Field(None, description="Email values to resolve or create")

    # Canonical flag ids + denormalized bool resolved server-side
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical")
    active: bool | None = Field(None, description="Denormalized profile_active flag state; resolved to a flag_ids entry server-side")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    email_ids: list[UUID] | None = Field(None, description="Email resource UUIDs")
    role: str | None = Field(None, description="Role name to resolve (single-name shortcut; legacy)")
    role_id: UUID | None = Field(None, description="Role resource UUID")
    role_draft: ProfileRoleDraftValue | None = Field(None, description="Inline-creatable role; id=null asks server to create with permissions/limits")
    primary_department_id: UUID | None = Field(None, description="UUID of the department to designate as primary")
    pending_ids: list[UUID] | None = Field(None, description="Resources to keep dormant")
    idempotency_key: UUID | None = Field(None, description="Idempotency key for draft writes")
    soft: bool = Field(False, description="Stage the draft dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Whether to accept the pending draft state")


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    name: str | None = Field(None, description="Resolved name value")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed profile_active flag state")
    departments: list[str] = Field(default_factory=list, description="Resolved department names")
    department_ids: list[UUID] = Field(..., description="Assigned department UUIDs")
    emails: list[str] = Field(default_factory=list, description="Resolved email values")
    email_ids: list[UUID] = Field(..., description="Assigned email resource UUIDs")
    role: str | None = Field(None, description="Assigned role name")
    role_id: UUID | None = Field(None, description="Assigned role resource UUID")
    role_draft: ProfileRoleDraftValue | None = Field(None, description="Echoed role draft with resolved request_limit_ids after inline-create")
    primary_department_id: UUID | None = Field(None, description="Assigned primary department UUID")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource UUIDs")


ProfileDraftFormState = DraftFormState


class PatchProfileDraftApiResponse(BaseModel):
    """Response model for new-style profile draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    idempotency_key: UUID | None = Field(None, description="Idempotency key for draft writes")
    message: str = Field(..., description="Result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


# ========== List Endpoint Types ==========


# ========== Export Endpoint Types ==========


class ExportProfileApiRequest(BaseModel):
    """Request model for profile export."""

    profile_export_id: UUID | None = Field(None, description="UUID of the profile to export")
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")


class ExportProfileApiResponse(BaseModel):
    """Response model for export profile endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


# ========== Emulate Endpoint Types ==========


class EmulateProfileApiRequest(BaseModel):
    """Request model for profile emulation."""

    target_profile_id: UUID | None = Field(None, description="UUID of the profile to emulate (omit on the ack call)")
    ttl_minutes: int | None = Field(120, description="Emulation duration in minutes")
    idempotency_key: UUID | None = Field(None, description="Idempotency / soft-call key. Echo the server-minted value with accept to promote/reject a staged emulation.")
    soft: bool = Field(False, description="Stage the emulation grant dormant (active=False) — it impersonates nothing until accepted")
    accept: bool | None = Field(None, description="Ack: True promotes the staged emulation, False rejects. Only meaningful with idempotency_key")


class EmulateProfileApiResponse(BaseModel):
    """Response model for profile emulation."""

    allowed: bool = Field(..., description="Whether emulation is allowed")
    reason: str | None = Field(None, description="Reason if emulation is denied")
    grant_id: UUID | None = Field(None, description="UUID of the emulation grant")
    expires_at: datetime | None = Field(None, description="When the emulation grant expires")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key (audit call_id). On a soft propose, echo this back with accept to promote/reject the staged emulation.")


# ========== Unemulate Endpoint Types ==========


class UnemulateProfileApiRequest(BaseModel):
    """Request model for exiting emulation of a specific profile."""

    target_profile_id: str | None = Field(None, description="Profile ID to stop emulating (omit on the ack call)")
    idempotency_key: UUID | None = Field(None, description="Idempotency / soft-call key. Echo the server-minted value with accept to perform/reject a proposed unemulation.")
    soft: bool = Field(False, description="Propose the unemulation without performing it — emulation continues until accepted (record-and-hold)")
    accept: bool | None = Field(None, description="Ack: True performs the proposed unemulation, False discards it. Only meaningful with idempotency_key")


class UnemulateProfileApiResponse(BaseModel):
    """Response model for exiting emulation (peel one layer)."""

    ok: bool = Field(..., description="Whether unemulation succeeded")
    reason: str | None = Field(None, description="Reason if unemulation failed")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key (audit call_id). On a soft propose, echo this back with accept to perform/reject the proposed unemulation.")


class ListProfilesApiProfile(BaseModel):
    """Profile type for list endpoint with computed permissions."""

    id: UUID | None = Field(None, description="Profile artifact UUID (canonical id; mirrors profile_id)")
    profile_id: UUID | None = Field(None, description="Unique profile identifier")
    emails: list[str] | None = Field(None, description="All email addresses for the profile")
    primary_email: str | None = Field(None, description="Primary email address")
    name: str | None = Field(None, description="Profile display name")
    role: str | None = Field(None, description="User role enum (e.g. admin, member, custom)")
    role_name: str | None = Field(None, description="Display name of the role (from roles_resource)")
    initials: str | None = Field(None, description="User initials for avatar display")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    primary_department_id: str | None = Field(None, description="Primary department ID")
    permission_ids: list[UUID] = Field(default_factory=list, description="Permission resource UUIDs granted via the profile's role")
    # Computed in Python
    can_edit: bool | None = Field(None, description="Whether the actor can edit this profile")
    can_duplicate: bool | None = Field(None, description="Whether the actor can duplicate this profile")
    can_delete: bool | None = Field(None, description="Whether the actor can delete this profile")
    can_emulate: bool | None = Field(None, description="Whether the actor can emulate this profile")
    is_emulated: bool | None = Field(None, description="Whether this profile is currently being emulated by the actor")
    is_inactive: bool | None = Field(None, description="Whether the profile is inactive")
    pending_status: str | None = Field(None, description="Pending soft_calls_entry status (e.g. 'pending')")
    pending_operation: str | None = Field(None, description="Pending operation (create/update/delete/duplicate)")
    pending_call_id: UUID | None = Field(None, description="Originating tool call id for ack")


class ListProfilesApiResponse(BaseModel):
    """Response model for profiles list endpoint with computed permissions."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    profiles: list[ListProfilesApiProfile] | None = Field(None, description="List of profile items")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments")
    role_filter: ListFilterSection | None = Field(None, description="Filter options for roles")
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
    permissions_filter: ListFilterSection | None = Field(None, description="Filter options for permissions in list UI")
    total_count: int | None = Field(None, description="Total number of profiles")


# ========== Context Endpoint Types ==========


# Re-export the canonical 40-field ThemePrimitives from utils so the wire
# type and the derivation input are the same model. Every field maps 1:1
# to a CSS variable in globals.css; all are optional (empty = inherit
# from globals.css default). ``destructive`` is the general error
# chrome (--destructive); ``danger`` is the analytics threshold color
# (--danger) — they're intentionally separate primitives.
from app.utils.settings.theme import ThemePrimitives  # noqa: E402,F401


class Thresholds(BaseModel):
    """Numeric score thresholds resolved from the active setting.

    Server pre-buckets dashboard metrics into ``success | warning | danger |
    neutral`` already, so most components don't need these values. Surface
    them for chart reference lines, tooltips, and any client-side bucketing.
    """

    success: int = Field(..., description="Score >= this counts as success")
    warning: int = Field(..., description="Score >= this counts as warning")
    danger: int = Field(..., description="Score < success threshold but >= this counts as danger; below is neutral/no-data")


class ThemeBundle(BaseModel):
    """Full theme payload for a page bootstrap.

    Riding along on every ``/{artifact}/context`` response via
    ``ProfileSummary.theme``. Layers:
      - ``primitives`` / ``dark_primitives`` — hex inputs the settings
        editor reads/writes (light + dark palettes).
      - ``tokens`` / ``dark_tokens`` — oklch tokens the client paints with.
        ``ThemeStyle`` emits two ``<style>`` blocks: one scoped to
        ``:root:not(.dark)`` (light) and one to ``:root.dark`` (dark).
      - ``thresholds`` — numeric score thresholds for analytics components.
    Empty-in → empty-out per token: missing values fall through to the
    matching ``globals.css`` default.
    """

    primitives: ThemePrimitives | None = Field(None, description="Hex inputs from the setting (light palette, for the theme editor)")
    tokens: ThemeTokens | None = Field(None, description="Derived oklch tokens for light mode (SSR CSS-var injection)")
    dark_primitives: ThemePrimitives | None = Field(None, description="Hex inputs from the setting (dark palette, for the theme editor)")
    dark_tokens: ThemeTokens | None = Field(None, description="Derived oklch tokens for dark mode (SSR CSS-var injection)")
    thresholds: Thresholds | None = Field(None, description="Score thresholds resolved from the setting")


class ProfileContextApiResponse(BaseModel):
    """Response for POST /context — identity + permissions + theme.

    Root-level layout route (mounted at /context).
    """

    # Identity
    id: UUID | None = Field(None, description="Profile UUID")
    name: str | None = Field(None, description="Profile display name")
    role: str | None = Field(None, description="User role (e.g. admin, user, viewer)")
    active: bool | None = Field(None, description="Whether the profile is active")

    # Routing & permissions
    role_artifacts: list[str] | None = Field(None, description="Artifact types accessible by role")
    scoped_roles: list[str] | None = Field(None, description="Roles scoped to the user")

    # Departments
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    primary_department_id: str | None = Field(None, description="Primary department ID")

    # Settings
    settings_id: str | None = Field(None, description="Active settings UUID")

    # Theme (raw color primitives from settings)
    theme: ThemePrimitives | None = Field(None, description="Theme color primitives from settings")

    # Session
    session_id: UUID | None = Field(None, description="Current session UUID")

    # Emulation
    is_emulation: bool | None = Field(None, description="Whether user is in emulation mode")
    emulation_depth: int | None = Field(None, description="Number of emulation layers deep")

    # Role resources (all roles — for emulation role display)
    role_resources: list[QGetProfileContextV4RoleResource] | None = Field(None, description="All role resources for display")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsProfileApiRequest(BaseModel):
    """Request model for profile generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GenerationsProfileListItem(BaseModel):
    """Single generation group in the profile generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsProfileApiResponse(BaseModel):
    """Response model for profile generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsProfileListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemProfileApiRequest(BaseModel):
    """Request model for profile problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemProfileApiResponse(BaseModel):
    """Response model for profile problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadProfileApiRequest(BaseModel):
    """Request model for profile text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadProfileApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadProfileApiRequest(BaseModel):
    """Request model for profile call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadProfileApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# ----------------------------------------------------------------------
# Resolve forward references for response models that mention
# ``ListProfilesApiProfile`` (defined later in this module). With
# ``from __future__ import annotations`` Pydantic reads the field
# annotations as strings and only resolves them on rebuild.
# ----------------------------------------------------------------------

CreateProfileApiResponse.model_rebuild()
UpdateProfileApiResponse.model_rebuild()
DuplicateProfileApiResponse.model_rebuild()


class FileDownloadProfileApiRequest(BaseModel):
    """Request model for profile file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadProfileApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
