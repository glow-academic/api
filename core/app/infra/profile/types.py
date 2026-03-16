"""Handcrafted types for profile artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.profile.create import CreateProfileItem
from app.infra.shared_types import QGetProfileContextV4RoleResource
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.profile_drafts.types import GetProfileDraftResponse

# ---------------------------------------------------------------------------
# Handcrafted resource types (replaces Q types from app.sql.types)
# ---------------------------------------------------------------------------


class ProfileNameResource(BaseModel):
    """Name resource for profile."""

    id: UUID | None = Field(None, description="Unique resource identifier")
    name: str | None = Field(None, description="Profile display name")
    generated: bool | None = Field(None, description="Whether the name was AI-generated")


class ProfileEmailResource(BaseModel):
    """Email resource for profile."""

    id: UUID | None = Field(None, description="Unique resource identifier")
    email: str | None = Field(None, description="Email address")
    generated: bool | None = Field(None, description="Whether the email was AI-generated")


class ProfileRequestLimitResource(BaseModel):
    """Request limit resource for profile."""

    id: UUID | None = Field(None, description="Unique resource identifier")
    requests_per_day: int | None = Field(None, description="Maximum requests allowed per day")
    generated: bool | None = Field(None, description="Whether the limit was AI-generated")


class ProfileDepartmentResource(BaseModel):
    """Department resource for profile."""

    id: UUID | None = Field(None, description="Unique resource identifier")
    name: str | None = Field(None, description="Department display name")
    description: str | None = Field(None, description="Department description text")
    generated: bool | None = Field(None, description="Whether the resource was AI-generated")


class ProfileRoleResource(BaseModel):
    """Role resource for profile."""

    id: UUID | None = Field(None, description="Unique resource identifier")
    role: str | None = Field(None, description="Role key (e.g. admin, user, viewer)")
    name: str | None = Field(None, description="Role display name")
    description: str | None = Field(None, description="Role description text")
    icon_value: str | None = Field(None, description="Icon identifier for the role")
    color_hex: str | None = Field(None, description="Hex color code for the role")


class ProfileFlagConfig(BaseModel):
    """Enriched profile flag config for direct client consumption."""

    key: str = Field(..., description="Flag key identifier")
    label: str = Field(..., description="Human-readable flag label")
    description: str | None = Field(None, description="Flag description text")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="UUID of the selected flag option")
    show: bool = Field(True, description="Whether the flag is visible to the client")
    required: bool = Field(False, description="Whether the flag is required")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")


class ProfileDraftEntry(BaseModel):
    """Draft entry for profile."""

    id: UUID | None = Field(None, description="Unique draft identifier")
    version: int | None = Field(None, description="Draft version number")
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
    request_limit_ids: list[UUID] | None = Field(None, description="Request limit resource UUIDs in the draft")
    role_ids: list[UUID] | None = Field(None, description="Role resource UUIDs in the draft")


# ---------------------------------------------------------------------------
# Section types
# ---------------------------------------------------------------------------


class ProfileNameSection(BaseResourceSection):
    resource: ProfileNameResource | None = Field(None, description="Currently selected name resource")
    resources: list[ProfileNameResource] | None = Field(None, description="Available name resources")


class ProfileRequestLimitSection(BaseResourceSection):
    resource: ProfileRequestLimitResource | None = Field(None, description="Currently selected request limit")
    resources: list[ProfileRequestLimitResource] | None = Field(None, description="Available request limit resources")


class ProfileFlagSection(BaseResourceSection):
    current: ProfileFlagConfig | None = Field(None, description="Currently selected flag config")
    resources: list[ProfileFlagConfig] | None = Field(None, description="Available flag configs")


class ProfileEmailSection(BaseResourceSection):
    current: list[ProfileEmailResource] | None = Field(None, description="Currently assigned emails")
    resources: list[ProfileEmailResource] | None = Field(None, description="Available email resources")


class ProfileDepartmentSection(BaseResourceSection):
    current: list[ProfileDepartmentResource] | None = Field(None, description="Currently assigned departments")
    resources: list[ProfileDepartmentResource] | None = Field(None, description="Available department resources")


class ProfileRoleSection(BaseResourceSection):
    current: list[ProfileRoleResource] | None = Field(None, description="Currently assigned roles")
    resources: list[ProfileRoleResource] | None = Field(None, description="Available role resources")


# ---------------------------------------------------------------------------
# GET endpoint types
# ---------------------------------------------------------------------------


class GetProfileApiRequest(BaseModel):
    target_profile_id: UUID | None = Field(None, description="UUID of the profile to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load")


class GetProfileApiResponse(BaseModel):
    actor_name: str | None = Field(None, description="Display name of the acting user")
    profile_exists: bool | None = Field(None, description="Whether the profile exists")
    can_edit: bool | None = Field(None, description="Whether the actor can edit this profile")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled, if any")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Group UUID for draft collaboration")
    profile_id: UUID | None = Field(None, description="UUID of the profile")

    role: str | None = Field(None, description="Current role of the profile")
    role_options: list[str] | None = Field(None, description="Available role options")

    basic_show_ai_generate: bool | None = Field(None, description="Whether to show basic AI generate button")
    general_show_ai_generate: bool | None = Field(None, description="Whether to show general AI generate button")

    names: ProfileNameSection | None = Field(None, description="Name section with resources")
    emails: ProfileEmailSection | None = Field(None, description="Email section with resources")
    request_limits: ProfileRequestLimitSection | None = Field(None, description="Request limit section with resources")
    flags: ProfileFlagSection | None = Field(None, description="Flag section with configs")
    departments: ProfileDepartmentSection | None = Field(None, description="Department section with resources")
    roles: ProfileRoleSection | None = Field(None, description="Role section with resources")


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


class CreateProfileApiRequest(BaseModel):
    """Request model for bulk create profile endpoint."""

    profiles: list[CreateProfileItem] = Field(..., description="List of profiles to create")


class CreateProfileApiResponse(BaseModel):
    """Response model for bulk create profile endpoint."""

    results: list[ProfileResultItem] = Field(..., description="Per-item creation results")


# ========== Update Endpoint Types ==========


class UpdateProfileItem(BaseModel):
    """Single profile item for update — profile_id required, all fields optional."""

    profile_id: UUID = Field(..., description="UUID of the profile to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Name value to resolve or create")
    request_limit_id: UUID | None = Field(None, description="UUID of the request limit resource")
    flag_id: UUID | None = Field(None, description="UUID of the flag option")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    email_ids: list[UUID] | None = Field(None, description="Email resource UUIDs")
    role_ids: list[UUID] | None = Field(None, description="Role resource UUIDs")


class UpdateProfileApiRequest(BaseModel):
    """Request model for bulk update profile endpoint."""

    profiles: list[UpdateProfileItem] = Field(..., description="List of profiles to update")


class UpdateProfileApiResponse(BaseModel):
    """Response model for bulk update profile endpoint."""

    results: list[ProfileResultItem] = Field(..., description="Per-item update results")


class SaveProfileFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Validation error message")


class DeleteProfileApiRequest(BaseModel):
    """Request model for bulk delete profile endpoint."""

    profile_ids: list[UUID] = Field(..., description="UUIDs of profiles to delete")


class DeleteProfileResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    profile_id: UUID = Field(..., description="UUID of the deleted profile")
    message: str = Field(..., description="Result message")


class DeleteProfileApiResponse(BaseModel):
    """Response model for bulk delete profile endpoint."""

    results: list[DeleteProfileResult] = Field(..., description="Per-item deletion results")


class DuplicateProfileApiRequest(BaseModel):
    target_profile_id: UUID = Field(..., description="UUID of the profile to duplicate")


class DuplicateProfileApiResponse(BaseModel):
    success: bool = Field(..., description="Whether the duplication succeeded")
    profile_id: UUID = Field(..., description="UUID of the newly created profile")
    message: str = Field(..., description="Result message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchProfileDraftApiRequest(BaseModel):
    """Request model for new-style profile draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id
    ID-only for non-creatable resources:
      - flag_id, department_ids, email_ids, role_ids, request_limit_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to update")
    expected_version: int = Field(0, description="Expected draft version for optimistic locking")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to resolve or create")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    email: str | None = Field(None, description="Email value to resolve or create")
    request_limit: int | None = Field(None, description="Request limit value to resolve or create")

    # Non-creatable — ID-only
    flag_id: UUID | None = Field(None, description="UUID of the flag option")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to assign")
    email_ids: list[UUID] | None = Field(None, description="Email resource UUIDs")
    role_ids: list[UUID] | None = Field(None, description="Role resource UUIDs")
    request_limit_ids: list[UUID] | None = Field(None, description="Request limit resource UUIDs")


class ProfileDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="Resolved name resource UUID")
    flag_id: UUID | None = Field(None, description="Resolved flag option UUID")
    department_ids: list[UUID] = Field(..., description="Assigned department UUIDs")
    email_ids: list[UUID] = Field(..., description="Assigned email resource UUIDs")
    role_ids: list[UUID] = Field(..., description="Assigned role resource UUIDs")
    request_limit_ids: list[UUID] = Field(..., description="Assigned request limit UUIDs")


class PatchProfileDraftApiResponse(BaseModel):
    """Response model for new-style profile draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    new_version: int = Field(..., description="New draft version after save")
    message: str = Field(..., description="Result message")
    form_state: ProfileDraftFormState | None = Field(None, description="Server-authoritative form state")


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
    role: str | None = Field(None, description="User role (e.g. admin, user, viewer)")
    initials: str | None = Field(None, description="User initials for avatar display")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    primary_department_id: str | None = Field(None, description="Primary department ID")
    requests_per_day: int | None = Field(None, description="Maximum requests allowed per day")
    # Computed in Python
    can_edit: bool | None = Field(None, description="Whether the actor can edit this profile")
    can_duplicate: bool | None = Field(None, description="Whether the actor can duplicate this profile")
    can_delete: bool | None = Field(None, description="Whether the actor can delete this profile")


class ListProfilesApiResponse(BaseModel):
    """Response model for profiles list endpoint with computed permissions."""

    actor_name: str | None = Field(None, description="Display name of the acting user")
    profiles: list[ListProfilesApiProfile] | None = Field(None, description="List of profile items")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments")
    role_filter: ListFilterSection | None = Field(None, description="Filter options for roles")
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

    Root-level layout route (mounted at /v5/context).
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
