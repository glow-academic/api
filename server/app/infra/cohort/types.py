"""Cohort API types - handcrafted types for cohort endpoints.

These types are used for the cohort API endpoints and include
SQL-computed permissions and UI flags.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.cohort.create import CreateCohortItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.cohort_drafts.types import GetCohortDraftResponse
from app.tools.resources.personas.types import GetPersonaResponse


class GetCohortDraftsApiResponse(BaseModel):
    """Response model for cohort drafts list endpoint."""

    entries: list[GetCohortDraftResponse] | None = Field(None, description="List of cohort draft entries")


# =============================================================================
# Resource Types (imported from SQL types for reuse)
# =============================================================================


class CohortNameResource(BaseModel):
    """Name resource for cohort."""

    id: UUID | None = Field(None, description="Unique identifier")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class CohortDescriptionResource(BaseModel):
    """Description resource for cohort."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class CohortFlagConfig(BaseModel):
    """Flag config for cohort — matches client FlagConfig interface."""

    key: str | None = Field(None, description="Flag key identifier")
    label: str | None = Field(None, description="Display label")
    description: str | None = Field(None, description="Flag description")
    icon_id: str | None = Field(None, description="Icon identifier for the flag")
    flag_option_id: UUID | None = Field(None, description="Selected flag option UUID")
    show: bool | None = Field(None, description="Whether to show this flag in the UI")
    required: bool | None = Field(None, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class CohortDepartment(BaseModel):
    """Department for cohort."""

    department_id: UUID | None = Field(None, description="Department UUID")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class CohortSimulation(BaseModel):
    """Simulation for cohort."""

    simulation_id: UUID | None = Field(None, description="Simulation UUID")
    name: str | None = Field(None, description="Simulation name")
    description: str | None = Field(None, description="Simulation description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class CohortSimulationPosition(BaseModel):
    """Simulation position for cohort."""

    simulation_id: UUID | None = Field(None, description="Associated simulation UUID")
    value: int | None = Field(None, description="Position value")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")


class CohortSimulationAvailability(BaseModel):
    """Simulation availability for cohort."""

    id: UUID | None = Field(None, description="Unique identifier")
    simulation_id: UUID | None = Field(None, description="Associated simulation UUID")
    time: datetime | None = Field(None, description="Availability time slot")
    type: str | None = Field(None, description="Availability type")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")


class CohortProfile(BaseModel):
    """Profile for cohort."""

    profile_id: UUID | None = Field(None, description="Profile UUID")
    name: str | None = Field(None, description="Profile name")
    description: str | None = Field(None, description="Profile description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")


class CohortProfilePersona(BaseModel):
    """Profile persona for cohort."""

    id: UUID | None = Field(None, description="Unique identifier")
    profile_id: UUID | None = Field(None, description="Associated profile UUID")
    persona_id: UUID | None = Field(None, description="Associated persona UUID")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")


# =============================================================================
# Resource Buckets (for WebSocket Jinja context)
# =============================================================================


class CohortResourceBucket(BaseModel):
    """Generic resources bucket with full objects (always plural lists)."""

    names: list[CohortNameResource] | None = Field(None, description="List of name resources")
    descriptions: list[CohortDescriptionResource] | None = Field(None, description="List of description resources")
    flags: list[CohortFlagConfig] | None = Field(None, description="List of flag config resources")
    departments: list[CohortDepartment] | None = Field(None, description="List of department resources")
    simulations: list[CohortSimulation] | None = Field(None, description="List of simulation resources")
    simulation_positions: list[CohortSimulationPosition] | None = Field(None, description="List of simulation position resources")
    simulation_availability: list[CohortSimulationAvailability] | None = Field(None, description="List of simulation availability resources")
    profiles: list[CohortProfile] | None = Field(None, description="List of profile resources")
    profile_personas: list[CohortProfilePersona] | None = Field(None, description="List of profile persona resources")
    personas: list[GetPersonaResponse] | None = Field(None, description="List of persona resources")


class CohortResources(BaseModel):
    """Full resources + current selections."""

    resources: CohortResourceBucket | None = Field(None, description="All available resources")
    current: CohortResourceBucket | None = Field(None, description="Currently selected resources")


# =============================================================================
# GET Endpoint Types
# =============================================================================


class GetCohortApiRequest(BaseModel):
    """Request for getting a single cohort."""

    cohort_id: UUID | None = Field(None, description="Cohort UUID to retrieve")
    descriptions_search: str | None = Field(None, description="Search query for descriptions")
    simulation_search: str | None = Field(None, description="Search query for simulations")
    simulation_show_selected: bool | None = Field(None, description="Whether to show only selected simulations")
    profile_search: str | None = Field(None, description="Search query for profiles")
    profile_show_selected: bool | None = Field(None, description="Whether to show only selected profiles")
    draft_id: UUID | None = Field(None, description="Draft UUID to load from")


class CohortNameSection(BaseResourceSection):
    resource: CohortNameResource | None = Field(None, description="Currently selected name resource")
    resources: list[CohortNameResource] | None = Field(None, description="Available name resources")


class CohortDescriptionSection(BaseResourceSection):
    resource: CohortDescriptionResource | None = Field(None, description="Currently selected description resource")
    resources: list[CohortDescriptionResource] | None = Field(None, description="Available description resources")


class CohortFlagSection(BaseResourceSection):
    resource: CohortFlagConfig | None = Field(None, description="Currently selected flag config")
    resources: list[CohortFlagConfig] | None = Field(None, description="Available flag configs")


class CohortDepartmentSection(BaseResourceSection):
    current: list[CohortDepartment] | None = Field(None, description="Currently selected departments")
    resources: list[CohortDepartment] | None = Field(None, description="Available departments")


class CohortSimulationSection(BaseResourceSection):
    current: list[CohortSimulation] | None = Field(None, description="Currently selected simulations")
    resources: list[CohortSimulation] | None = Field(None, description="Available simulations")


class CohortSimulationPositionSection(BaseResourceSection):
    current: list[CohortSimulationPosition] | None = Field(None, description="Currently selected simulation positions")
    resources: list[CohortSimulationPosition] | None = Field(None, description="Available simulation positions")


class CohortSimulationAvailabilitySection(BaseResourceSection):
    current: list[CohortSimulationAvailability] | None = Field(None, description="Currently selected availability slots")
    resources: list[CohortSimulationAvailability] | None = Field(None, description="Available availability slots")


class CohortProfileSection(BaseResourceSection):
    current: list[CohortProfile] | None = Field(None, description="Currently selected profiles")
    resources: list[CohortProfile] | None = Field(None, description="Available profiles")


class CohortProfilePersonaSection(BaseResourceSection):
    current: list[CohortProfilePersona] | None = Field(None, description="Currently selected profile personas")
    resources: list[CohortProfilePersona] | None = Field(None, description="Available profile personas")


class GetCohortApiResponse(BaseModel):
    """Response for getting a single cohort."""

    # Context
    actor_name: str | None = Field(None, description="Display name of the current user")
    cohort_exists: bool | None = Field(None, description="Whether the cohort exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason editing is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="Associated group UUID")

    # Step-level AI generation flags
    basic_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for basic step")
    simulations_step_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for simulations step")
    profiles_step_show_ai_generate: bool | None = Field(None, description="Whether to show AI generate for profiles step")

    names: CohortNameSection | None = Field(None, description="Name section with resource and options")
    descriptions: CohortDescriptionSection | None = Field(None, description="Description section with resource and options")
    flags: CohortFlagSection | None = Field(None, description="Flag section with resource and options")
    departments: CohortDepartmentSection | None = Field(None, description="Department section with selections and options")
    simulations: CohortSimulationSection | None = Field(None, description="Simulation section with selections and options")
    simulation_positions: CohortSimulationPositionSection | None = Field(None, description="Simulation position section")
    simulation_availability: CohortSimulationAvailabilitySection | None = Field(None, description="Simulation availability section")
    profiles: CohortProfileSection | None = Field(None, description="Profile section with selections and options")
    profile_personas: CohortProfilePersonaSection | None = Field(None, description="Profile persona section")
    personas: list[GetPersonaResponse] | None = Field(None, description="List of available personas")


# =============================================================================
# LIST Endpoint Types
# =============================================================================


class ListCohortApiCohort(BaseModel):
    """Cohort item in list response with Python-computed permissions."""

    cohort_id: UUID | None = Field(None, description="Cohort UUID")
    name: str | None = Field(None, description="Cohort name")
    description: str | None = Field(None, description="Cohort description")
    is_inactive: bool | None = Field(None, description="Whether the cohort is inactive")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    profile_ids: list[str] | None = Field(None, description="Associated profile IDs")
    simulation_ids: list[str] | None = Field(None, description="Associated simulation IDs")
    usage_count: int | None = Field(None, description="Number of times this cohort is used")
    num_members: int | None = Field(None, description="Number of members in the cohort")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_leave: bool | None = Field(None, description="Whether the current user can leave")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")


class ListCohortApiProfile(BaseModel):
    """Profile in list response."""

    profile_id: UUID | None = Field(None, description="Profile UUID")
    name: str | None = Field(None, description="Profile name")
    description: str | None = Field(None, description="Profile description")


class ListCohortApiSimulation(BaseModel):
    """Simulation in list response."""

    simulation_id: UUID | None = Field(None, description="Simulation UUID")
    name: str | None = Field(None, description="Simulation name")
    description: str | None = Field(None, description="Simulation description")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")


class ListCohortApiDepartment(BaseModel):
    """Department in list response."""

    department_id: UUID | None = Field(None, description="Department UUID")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")


class ListCohortApiResponse(BaseModel):
    """Response for listing cohorts."""

    actor_name: str | None = Field(None, description="Display name of the current user")
    user_role: str | None = Field(None, description="Role of the current user")
    cohorts: list[ListCohortApiCohort] | None = Field(None, description="List of cohorts")
    profiles: list[ListCohortApiProfile] | None = Field(None, description="List of profiles for filtering")
    simulations: list[ListCohortApiSimulation] | None = Field(None, description="List of simulations for filtering")
    departments: list[ListCohortApiDepartment] | None = Field(None, description="List of departments for filtering")
    simulation_filter: "ListFilterSection | None" = Field(None, description="Filter options for simulations in list UI")
    profile_filter: "ListFilterSection | None" = Field(None, description="Filter options for profiles in list UI")
    department_filter: "ListFilterSection | None" = Field(None, description="Filter options for departments in list UI")
    flag_filter: "ListFilterSection | None" = Field(None, description="Filter options for flags in list UI")
    total_count: int | None = Field(None, description="Total number of matching records")


# =============================================================================
# Resource Action Types (used by draft endpoint)
# =============================================================================


# =============================================================================
# Shared Create/Update Types
# =============================================================================


class CohortFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


class CohortResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    cohort_id: UUID | None = Field(None, description="Cohort UUID")
    message: str = Field(..., description="Human-readable result message")
    errors: list[CohortFieldError] | None = Field(None, description="List of per-field errors")


# =============================================================================
# Create Endpoint Types
# =============================================================================


class CreateCohortApiRequest(BaseModel):
    """Request model for bulk create cohort endpoint."""

    cohorts: list[CreateCohortItem] = Field(..., description="List of cohorts to create")


class CreateCohortApiResponse(BaseModel):
    """Response model for bulk create cohort endpoint."""

    results: list[CohortResultItem] = Field(..., description="List of operation results")


# =============================================================================
# Update Endpoint Types
# =============================================================================


class UpdateCohortItem(BaseModel):
    """Single cohort item for update — cohort_id required, all fields optional."""

    cohort_id: UUID = Field(..., description="Cohort UUID to update")  # Required — which cohort to update
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Single-select flag
    flag_id: UUID | None = Field(None, description="Flag option UUID")
    # Multi-select IDs
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation UUIDs")
    simulation_position_ids: list[UUID] | None = Field(None, description="Simulation position UUIDs")
    simulation_availability_ids: list[UUID] | None = Field(None, description="Simulation availability UUIDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs")
    profile_persona_ids: list[UUID] | None = Field(None, description="Profile persona UUIDs")
    # Value-based fields (for CSV import — resolved to IDs)
    is_inactive: bool | None = Field(None, description="Whether the cohort is inactive")
    departments: list[str] | None = Field(None, description="Department names for resolution")
    simulations: list[str] | None = Field(None, description="Simulation names for resolution")
    profiles: list[str] | None = Field(None, description="Profile names for resolution")


class UpdateCohortApiRequest(BaseModel):
    """Request model for bulk update cohort endpoint."""

    cohorts: list[UpdateCohortItem] = Field(..., description="List of cohorts to update")


class UpdateCohortApiResponse(BaseModel):
    """Response model for bulk update cohort endpoint."""

    results: list[CohortResultItem] = Field(..., description="List of operation results")


class SaveCohortFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


# =============================================================================
# DELETE Endpoint Types
# =============================================================================


class DeleteCohortApiRequest(BaseModel):
    """Request model for bulk delete cohort endpoint."""

    cohort_ids: list[UUID] = Field(..., description="Cohort UUIDs to delete")


class DeleteCohortResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    cohort_id: UUID = Field(..., description="Cohort UUID")
    message: str = Field(..., description="Human-readable result message")


class DeleteCohortApiResponse(BaseModel):
    """Response model for bulk delete cohort endpoint."""

    results: list[DeleteCohortResult] = Field(..., description="List of operation results")


# =============================================================================
# DUPLICATE Endpoint Types
# =============================================================================


class DuplicateCohortApiRequest(BaseModel):
    """Request for duplicating a cohort."""

    cohort_id: UUID = Field(..., description="Cohort UUID to duplicate")


class DuplicateCohortApiResponse(BaseModel):
    """Response for duplicating a cohort."""

    success: bool = Field(..., description="Whether the operation succeeded")
    cohort_id: UUID = Field(..., description="Newly created cohort UUID")
    message: str = Field(..., description="Human-readable result message")


# =============================================================================
# DRAFT Endpoint Types
# =============================================================================


class DraftSimulationPositionValue(BaseModel):
    """Value for creating a simulation_position resource via draft."""

    simulation_id: UUID = Field(..., description="Associated simulation UUID")
    value: int = Field(..., description="Position value")


class DraftSimulationAvailabilityValue(BaseModel):
    """Value for creating a simulation_availability resource via draft."""

    simulation_id: UUID = Field(..., description="Associated simulation UUID")
    time: datetime = Field(..., description="Availability time slot")
    type: str = Field(..., description="Availability type")


class DraftProfilePersonaValue(BaseModel):
    """Value for creating a profile_persona resource via draft."""

    profile_id: UUID = Field(..., description="Associated profile UUID")
    persona_id: UUID = Field(..., description="Associated persona UUID")


class PatchCohortDraftApiRequest(BaseModel):
    """Request model for new-style cohort draft endpoint.

    Dual-mode for creatable resources:
      - Single-select: name/name_id, description/description_id
      - Multi-select compound: simulation_positions, simulation_availability,
        profile_personas (values create resources, created IDs merged with existing IDs)
    ID-only for non-creatable resources:
      - flag_id, department_ids, simulation_ids, profile_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to patch")
    expected_version: int = Field(0, description="Expected draft version for concurrency control")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to create a resource")
    name_id: UUID | None = Field(None, description="Existing name resource UUID")
    description: str | None = Field(None, description="Description value to create a resource")
    description_id: UUID | None = Field(None, description="Existing description resource UUID")

    # Non-creatable — ID-only
    flag_id: UUID | None = Field(None, description="Flag option UUID")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation UUIDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs")

    # Creatable multi-select compound — values create resources, IDs merged
    simulation_position_ids: list[UUID] | None = Field(None, description="Existing simulation position UUIDs")
    simulation_positions: list[DraftSimulationPositionValue] | None = Field(None, description="Simulation position values to create")
    simulation_availability_ids: list[UUID] | None = Field(None, description="Existing simulation availability UUIDs")
    simulation_availability: list[DraftSimulationAvailabilityValue] | None = Field(None, description="Simulation availability values to create")
    profile_persona_ids: list[UUID] | None = Field(None, description="Existing profile persona UUIDs")
    profile_personas: list[DraftProfilePersonaValue] | None = Field(None, description="Profile persona values to create")


class CohortDraftFormState(BaseModel):
    """Full form state after draft patch — server is source of truth.

    Client replaces its local form state with this after every successful patch.
    """

    name_id: UUID | None = Field(None, description="Selected name resource UUID")
    description_id: UUID | None = Field(None, description="Selected description resource UUID")
    flag_id: UUID | None = Field(None, description="Selected flag option UUID")
    department_ids: list[UUID] = Field(default_factory=list, description="Selected department UUIDs")
    simulation_ids: list[UUID] = Field(default_factory=list, description="Selected simulation UUIDs")
    simulation_position_ids: list[UUID] = Field(default_factory=list, description="Selected simulation position UUIDs")
    simulation_availability_ids: list[UUID] = Field(default_factory=list, description="Selected simulation availability UUIDs")
    profile_ids: list[UUID] = Field(default_factory=list, description="Selected profile UUIDs")
    profile_persona_ids: list[UUID] = Field(default_factory=list, description="Selected profile persona UUIDs")


class PatchCohortDraftApiResponse(BaseModel):
    """Response model for new-style cohort draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="Draft UUID")
    new_version: int = Field(..., description="New draft version number after patch")
    message: str = Field(..., description="Human-readable result message")
    form_state: CohortDraftFormState | None = Field(None, description="Server-authoritative form state")


# =============================================================================
# EXPORT Endpoint Types
# =============================================================================


class ExportCohortApiRequest(BaseModel):
    """Request model for export cohort endpoint."""

    search: str | None = Field(None, description="Search query text")
    filter_simulation_ids: list[str] | None = Field(None, description="Simulation IDs to filter by")
    filter_profile_ids: list[str] | None = Field(None, description="Profile IDs to filter by")
    filter_department_ids: list[str] | None = Field(None, description="Department IDs to filter by")


class ExportCohortApiResponse(BaseModel):
    """Response model for export cohort endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# SQL Row Types (for internal use)
# =============================================================================
# Note: GetCohortAccessSqlParams, GetCohortAccessSqlRow, GetCohortIdsSqlParams,
# and GetCohortIdsSqlRow are now auto-generated in app/sql/types.py from the
# corresponding SQL files in app/v5/sql/queries/cohorts/


class ListCohortSqlCohort(BaseModel):
    """Raw cohort from SQL — permissions computed in Python."""

    cohort_id: UUID | None = Field(None, description="Cohort UUID")
    name: str | None = Field(None, description="Cohort name")
    description: str | None = Field(None, description="Cohort description")
    is_inactive: bool | None = Field(None, description="Whether the cohort is inactive")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    profile_ids: list[str] | None = Field(None, description="Associated profile IDs")
    simulation_ids: list[str] | None = Field(None, description="Associated simulation IDs")
    usage_count: int | None = Field(None, description="Number of times this cohort is used")
    num_members: int | None = Field(None, description="Number of members in the cohort")
    is_member: bool | None = Field(None, description="Whether the current user is a member")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")
