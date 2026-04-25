"""Handcrafted types for profile artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.shared_types import QGetProfileContextV4RoleResource
from app.infra.api_types import ListFilterSection
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.profile_drafts.types import GetProfileDraftResponse

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

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
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

    profiles: list[CreateProfileItem] = Field(..., description="List of profiles to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateProfileApiResponse(BaseModel):
    """Response model for bulk create profile endpoint."""

    results: list[ProfileResultItem] = Field(..., description="Per-item creation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateProfileItem(ScopedItem):
    """Single profile item for update — profile_id required, all fields optional."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateProfileItem.RESOURCE_TYPE_MAP

    profile_id: UUID = Field(..., description="UUID of the profile to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    # Canonical flag ids + denormalized bool
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Denormalized profile_active flag state")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    email_ids: list[UUID] | None = Field(None, description="Email resource UUIDs")
    role_id: UUID | None = Field(None, description="Role resource UUID")
    primary_department_id: UUID | None = Field(None, description="UUID of the department to designate as primary")


class UpdateProfileApiRequest(BaseModel):
    """Request model for bulk update profile endpoint."""

    profiles: list[UpdateProfileItem] = Field(..., description="List of profiles to update")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateProfileApiResponse(BaseModel):
    """Response model for bulk update profile endpoint."""

    results: list[ProfileResultItem] = Field(..., description="Per-item update results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveProfileFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class DeleteProfileApiRequest(BaseModel):
    """Request model for bulk delete profile endpoint."""

    profile_ids: list[UUID] = Field(..., description="UUIDs of profiles to delete")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteProfileResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    profile_id: UUID = Field(..., description="UUID of the deleted profile")
    message: str = Field(..., description="Result message")


class DeleteProfileApiResponse(BaseModel):
    """Response model for bulk delete profile endpoint."""

    results: list[DeleteProfileResult] = Field(..., description="Per-item deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateProfileApiRequest(BaseModel):
    target_profile_id: UUID = Field(..., description="UUID of the profile to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateProfileApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    profile_id: UUID = Field(..., description="UUID of the newly created profile")
    message: str = Field(..., description="Result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


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
    name: str | None = Field(None, description="Name value to resolve or create")
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
    accept: bool = Field(True, description="Whether to accept the pending draft state")


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


class ExportProfileApiResponse(BaseModel):
    """Response model for export profile endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


# ========== Emulate Endpoint Types ==========


class EmulateProfileApiRequest(BaseModel):
    """Request model for profile emulation."""

    target_profile_id: UUID = Field(..., description="UUID of the profile to emulate")
    ttl_minutes: int | None = Field(120, description="Emulation duration in minutes")


class EmulateProfileApiResponse(BaseModel):
    """Response model for profile emulation."""

    allowed: bool = Field(..., description="Whether emulation is allowed")
    reason: str | None = Field(None, description="Reason if emulation is denied")
    grant_id: UUID | None = Field(None, description="UUID of the emulation grant")
    expires_at: datetime | None = Field(None, description="When the emulation grant expires")


# ========== Unemulate Endpoint Types ==========


class UnemulateProfileApiRequest(BaseModel):
    """Request model for exiting emulation of a specific profile."""

    target_profile_id: str = Field(..., description="Profile ID to stop emulating")


class UnemulateProfileApiResponse(BaseModel):
    """Response model for exiting emulation (peel one layer)."""

    ok: bool = Field(..., description="Whether unemulation succeeded")
    reason: str | None = Field(None, description="Reason if unemulation failed")


class ListProfilesApiProfile(BaseModel):
    """Profile type for list endpoint with computed permissions."""

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


class ThemePrimitives(BaseModel):
    """Raw theme color primitives (hex values) from settings.

    General-purpose — not CSS-specific. Clients derive their own
    presentation tokens (oklch, CSS variables, etc.) from these.
    """

    primary: str | None = Field(None, description="Primary color hex value")
    accent: str | None = Field(None, description="Accent color hex value")
    background: str | None = Field(None, description="Background color hex value")
    surface: str | None = Field(None, description="Surface color hex value")
    success: str | None = Field(None, description="Success state color hex value")
    warning: str | None = Field(None, description="Warning state color hex value")
    error: str | None = Field(None, description="Error state color hex value")
    chart1: str | None = Field(None, description="Chart color 1 hex value")
    chart2: str | None = Field(None, description="Chart color 2 hex value")
    chart3: str | None = Field(None, description="Chart color 3 hex value")
    chart4: str | None = Field(None, description="Chart color 4 hex value")
    chart5: str | None = Field(None, description="Chart color 5 hex value")


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
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemProfileApiResponse(BaseModel):
    """Response model for profile problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
