"""Cohort API types - handcrafted types for cohort endpoints.

These types are used for the cohort API endpoints and include
SQL-computed permissions and UI flags.
"""

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import BaseResourceSection, ListFilterSection
from app.infra.persona.types import ImportField
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.cohort_drafts.types import GetCohortDraftResponse
from app.tools.resources.personas.types import GetPersonaResponse


class GetCohortDraftsApiRequest(BaseModel):
    """Request model for the cohort drafts list endpoint.

    Mirrors ``GenerationsCohortApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


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
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class CohortDescriptionResource(BaseModel):
    """Description resource for cohort."""

    id: UUID | None = Field(None, description="Unique identifier")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class CohortFlagResource(BaseModel):
    """Flag option row for cohort — one per (name, type, value) flags_resource entry."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'cohort_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class CohortDepartment(BaseModel):
    """Department for cohort."""

    department_id: UUID | None = Field(None, description="Department UUID")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class CohortSimulation(BaseModel):
    """Simulation for cohort."""

    simulation_id: UUID | None = Field(None, description="Simulation UUID")
    name: str | None = Field(None, description="Simulation name")
    description: str | None = Field(None, description="Simulation description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class CohortSimulationPosition(BaseModel):
    """Simulation position for cohort."""

    id: UUID | None = Field(None, description="Unique identifier")
    simulation_id: UUID | None = Field(None, description="Associated simulation UUID")
    value: int | None = Field(None, description="Position value")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class CohortSimulationAvailability(BaseModel):
    """Simulation availability for cohort."""

    id: UUID | None = Field(None, description="Unique identifier")
    simulation_id: UUID | None = Field(None, description="Associated simulation UUID")
    time: datetime | None = Field(None, description="Availability time slot")
    type: str | None = Field(None, description="Availability type")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class CohortProfile(BaseModel):
    """Profile for cohort."""

    profile_id: UUID | None = Field(None, description="Profile UUID")
    name: str | None = Field(None, description="Profile name")
    description: str | None = Field(None, description="Profile description")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class CohortProfilePersona(BaseModel):
    """Profile persona for cohort."""

    id: UUID | None = Field(None, description="Unique identifier")
    profile_id: UUID | None = Field(None, description="Associated profile UUID")
    persona_id: UUID | None = Field(None, description="Associated persona UUID")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class CohortPersonaResource(BaseModel):
    """Persona option exposed from cohort GET."""

    id: UUID | None = Field(None, description="Persona UUID")
    name: str | None = Field(None, description="Persona name")
    description: str | None = Field(None, description="Persona description")
    icon: str | None = Field(None, description="Persona icon")
    color: str | None = Field(None, description="Persona color")
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    instructions: str | None = Field(None, description="Persona instructions")
    examples: list[str] | None = Field(None, description="Persona examples")
    parameter_field_ids: list[UUID] | None = Field(None, description="Associated parameter field UUIDs")
    active: bool | None = Field(None, description="Whether the persona is active")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether created via MCP")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


# =============================================================================
# Resource Buckets (for WebSocket Jinja context)
# =============================================================================


class CohortResourceBucket(BaseModel):
    """Generic resources bucket with full objects (always plural lists)."""

    names: list[CohortNameResource] | None = Field(None, description="List of name resources")
    descriptions: list[CohortDescriptionResource] | None = Field(None, description="List of description resources")
    flags: list[CohortFlagResource] | None = Field(None, description="List of flag config resources")
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


class SectionFilter(BaseModel):
    """Per-section filter options for GET requests."""

    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")
    parameter_ids: list[str] | None = Field(None, description="Reserved for parity with persona pattern")


class GetCohortApiRequest(BaseModel):
    """Request model for get cohort endpoint."""

    id: UUID | None = Field(None, description="Cohort UUID to retrieve")
    cohort_id: UUID | None = Field(None, description="Legacy alias for cohort UUID")
    draft_id: UUID | None = Field(None, description="Draft UUID to load from")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    simulations: SectionFilter | None = Field(None, description="Filter options for simulations section")
    simulation_positions: SectionFilter | None = Field(None, description="Filter options for simulation positions section")
    simulation_availability: SectionFilter | None = Field(None, description="Filter options for simulation availability section")
    profiles: SectionFilter | None = Field(None, description="Filter options for profiles section")
    profile_personas: SectionFilter | None = Field(None, description="Filter options for profile personas section")
    personas: SectionFilter | None = Field(None, description="Filter options for personas section")
    # Legacy top-level filters retained for compatibility while adapters migrate.
    descriptions_search: str | None = Field(None, description="Legacy search query for descriptions")
    simulation_search: str | None = Field(None, description="Legacy search query for simulations")
    simulation_show_selected: bool | None = Field(None, description="Legacy selected-only flag for simulations")
    profile_search: str | None = Field(None, description="Legacy search query for profiles")
    profile_show_selected: bool | None = Field(None, description="Legacy selected-only flag for profiles")


class CohortNameSection(BaseResourceSection):
    resource: CohortNameResource | None = Field(None, description="Currently selected name resource")
    resources: list[CohortNameResource] | None = Field(None, description="Available name resources")


class CohortDescriptionSection(BaseResourceSection):
    resource: CohortDescriptionResource | None = Field(None, description="Currently selected description resource")
    resources: list[CohortDescriptionResource] | None = Field(None, description="Available description resources")


class CohortFlagSection(BaseResourceSection):
    resource: CohortFlagResource | None = Field(None, description="Currently selected flag config")
    resources: list[CohortFlagResource] | None = Field(None, description="Available flag configs")


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
    group_id: UUID | None = Field(None, description="Associated group UUID")
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    show_ai_generate: bool | None = Field(None, description="Whether AI generation is available")

    names: list[CohortNameResource] | None = Field(None, description="Name resources with selected/suggested flags")
    descriptions: list[CohortDescriptionResource] | None = Field(None, description="Description resources with selected/suggested flags")
    flags: list[CohortFlagResource] | None = Field(None, description="Flag resources with selected/suggested flags")
    departments: list[CohortDepartment] | None = Field(None, description="Department resources with selected/suggested flags")
    simulations: list[CohortSimulation] | None = Field(None, description="Simulation resources with selected/suggested flags")
    simulation_positions: list[CohortSimulationPosition] | None = Field(None, description="Simulation position resources with selected/suggested flags")
    simulation_availability: list[CohortSimulationAvailability] | None = Field(None, description="Simulation availability resources with selected/suggested flags")
    profiles: list[CohortProfile] | None = Field(None, description="Profile resources with selected/suggested flags")
    profile_personas: list[CohortProfilePersona] | None = Field(None, description="Profile persona resources with selected/suggested flags")
    personas: list[CohortPersonaResource] | None = Field(None, description="Persona resources with selected/suggested flags")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource IDs from the draft, when available")
    # Legacy step flags retained for callers that still read them.
    basic_show_ai_generate: bool | None = Field(None, description="Legacy AI-generate flag for the basic step")
    simulations_step_show_ai_generate: bool | None = Field(None, description="Legacy AI-generate flag for the simulations step")
    profiles_step_show_ai_generate: bool | None = Field(None, description="Legacy AI-generate flag for the profiles step")


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
    pending_status: str | None = Field(None, description="Soft-call ledger status (pending/accepted/rejected) for the latest pending op on this row")
    pending_operation: str | None = Field(None, description="Operation name (create/update/delete/duplicate/draft) of the latest pending soft-call entry")
    pending_call_id: UUID | None = Field(None, description="Originating tool call id for the latest pending soft-call entry")


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
    import_fields: list[ImportField] | None = Field(
        None, description="CSV import column schema for the bulk-import dialog"
    )


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


class CreateCohortItem(ScopedItem):
    """Single cohort item for create — no cohort_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "flag_ids": "flags",
        "active": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "simulation_ids": "simulations",
        "simulations": "simulations",
        "simulation_position_ids": "simulation_positions",
        "simulation_availability_ids": "simulation_availability",
        "profile_ids": "profiles",
        "profiles": "profiles",
        "profile_persona_ids": "profile_personas",
    }

    id: UUID | None = Field(None, description="Optional pre-assigned UUID")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Canonical multi-select flag ids + denormalized boolean for cohort_active.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized cohort_active flag state; resolved to a flag_ids entry server-side")
    # Multi-select IDs
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation UUIDs")
    simulation_position_ids: list[UUID] | None = Field(None, description="Simulation position UUIDs")
    simulation_availability_ids: list[UUID] | None = Field(None, description="Simulation availability UUIDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs")
    profile_persona_ids: list[UUID] | None = Field(None, description="Profile persona UUIDs")
    # Value-based fields (for CSV import — resolved to IDs)
    departments: list[str] | None = Field(None, description="Department names for resolution")
    simulations: list[str] | None = Field(None, description="Simulation names for resolution")
    profiles: list[str] | None = Field(None, description="Profile names for resolution")


class CreateCohortApiRequest(BaseModel):
    """Request model for bulk create cohort endpoint."""

    cohorts: list[CreateCohortItem] = Field(..., description="List of cohorts to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    soft: bool = Field(False, description="Stage the create dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateCohortApiResponse(BaseModel):
    """Response model for bulk create cohort endpoint."""

    results: list[CohortResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# Update Endpoint Types
# =============================================================================


class UpdateCohortItem(ScopedItem):
    """Single cohort item for update — cohort_id required, all fields optional."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateCohortItem.RESOURCE_TYPE_MAP

    id: UUID = Field(..., description="Cohort UUID to update")  # Required — which cohort to update
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="Name resource UUID")
    name: str | None = Field(None, description="Name value for resolution")
    description_id: UUID | None = Field(None, description="Description resource UUID")
    description: str | None = Field(None, description="Description value for resolution")
    # Canonical multi-select flag ids + denormalized boolean for cohort_active.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized cohort_active flag state; resolved to a flag_ids entry server-side")
    # Multi-select IDs
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation UUIDs")
    simulation_position_ids: list[UUID] | None = Field(None, description="Simulation position UUIDs")
    simulation_availability_ids: list[UUID] | None = Field(None, description="Simulation availability UUIDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs")
    profile_persona_ids: list[UUID] | None = Field(None, description="Profile persona UUIDs")
    # Value-based fields (for CSV import — resolved to IDs)
    departments: list[str] | None = Field(None, description="Department names for resolution")
    simulations: list[str] | None = Field(None, description="Simulation names for resolution")
    profiles: list[str] | None = Field(None, description="Profile names for resolution")


class UpdateCohortPatch(UpdateCohortItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateCohortItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved cohort id per matched row",
    )


class UpdateCohortApiRequest(BaseModel):
    """Request model for bulk update cohort endpoint.

    Three body shapes:
      - First call (explicit): ``cohorts`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/cohort/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    cohorts: list[UpdateCohortItem] | None = Field(
        None, description="List of cohorts to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteCohortApiRequest; ``patch``
    # is the shared change set applied to every matched row. ``patch.id``
    # is ignored — each resolved id is stamped onto a clone before the
    # per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every cohort matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateCohortPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    filter_profile_ids: list[UUID] | None = Field(None, description="Filter by profile UUIDs")
    filter_simulation_ids: list[UUID] | None = Field(None, description="Filter by simulation UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    profile_search: str | None = Field(None, description="Search text for profile facet (no-op for row filtering)")
    simulation_search: str | None = Field(None, description="Search text for simulation facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    soft: bool = Field(False, description="Stage the update dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateCohortApiResponse(BaseModel):
    """Response model for bulk update cohort endpoint."""

    results: list[CohortResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveCohortFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Field name that has the error")
    message: str = Field(..., description="Human-readable error message")


# =============================================================================
# DELETE Endpoint Types
# =============================================================================


class DeleteCohortApiRequest(BaseModel):
    """Request model for bulk delete cohort endpoint.

    Three body shapes:
      - First call (explicit): ``cohort_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/cohort/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    cohort_ids: list[UUID] | None = Field(
        None, description="Cohort UUIDs to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchCohortApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every cohort matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /cohort/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``cohort_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    filter_profile_ids: list[UUID] | None = Field(None, description="Filter by profile UUIDs")
    filter_simulation_ids: list[UUID] | None = Field(None, description="Filter by simulation UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    profile_search: str | None = Field(None, description="Search text for profile facet (no-op for row filtering)")
    simulation_search: str | None = Field(None, description="Search text for simulation facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    soft: bool = Field(False, description="Stage the delete dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (confirm deletion) or reject (restore). Only meaningful with idempotency_key")


class DeleteCohortResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    cohort_id: UUID = Field(..., description="Cohort UUID")
    message: str = Field(..., description="Human-readable result message")


class DeleteCohortApiResponse(BaseModel):
    """Response model for bulk delete cohort endpoint."""

    results: list[DeleteCohortResult] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# DUPLICATE Endpoint Types
# =============================================================================


class DuplicateCohortApiRequest(BaseModel):
    """Request for duplicating a cohort."""

    cohort_id: UUID = Field(..., description="Cohort UUID to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    soft: bool = Field(False, description="Stage the duplicate dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateCohortApiResponse(BaseModel):
    """Response for duplicating a cohort."""

    success: bool = Field(..., description="Whether the operation succeeded")
    cohort_id: UUID = Field(..., description="Newly created cohort UUID")
    message: str = Field(..., description="Human-readable result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


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


class PatchCohortDraftApiRequest(ScopedItem):
    """Request model for cohort draft endpoint."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "simulation_ids": "simulations",
        "simulations": "simulations",
        "profile_ids": "profiles",
        "profiles": "profiles",
        "simulation_position_ids": "simulation_positions",
        "simulation_positions": "simulation_positions",
        "simulation_availability_ids": "simulation_availability",
        "simulation_availability": "simulation_availability",
        "profile_persona_ids": "profile_personas",
        "profile_personas": "profile_personas",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to patch")
    input_draft_id: UUID | None = Field(None, description="Legacy alias for existing draft UUID to patch")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Name value to create a resource")
    name_id: UUID | None = Field(None, description="Existing name resource UUID")
    description: str | None = Field(None, description="Description value to create a resource")
    description_id: UUID | None = Field(None, description="Existing description resource UUID")

    # Canonical multi-select flag ids + denormalized boolean for cohort_active.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized cohort_active flag state; resolved to a flag_ids entry server-side")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs")
    departments: list[str] | None = Field(None, description="Department names to resolve")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation UUIDs")
    simulations: list[str] | None = Field(None, description="Simulation names to resolve")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs")
    profiles: list[str] | None = Field(None, description="Profile names to resolve")

    # Creatable multi-select compound — values create resources, IDs merged
    simulation_position_ids: list[UUID] | None = Field(None, description="Existing simulation position UUIDs")
    simulation_positions: list[DraftSimulationPositionValue] | None = Field(None, description="Simulation position values to create")
    simulation_availability_ids: list[UUID] | None = Field(None, description="Existing simulation availability UUIDs")
    simulation_availability: list[DraftSimulationAvailabilityValue] | None = Field(None, description="Simulation availability values to create")
    profile_persona_ids: list[UUID] | None = Field(None, description="Existing profile persona UUIDs")
    profile_personas: list[DraftProfilePersonaValue] | None = Field(None, description="Profile persona values to create")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep as pending where supported by the tool layer")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack or retry")
    soft: bool = Field(False, description="Stage the draft dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept or reject dormant draft state")


class DraftFormState(BaseModel):
    """Full form state after draft patch — server is source of truth.

    Client replaces its local form state with this after every successful patch.
    """

    name_id: UUID | None = Field(None, description="Selected name resource UUID")
    name: str | None = Field(None, description="Name value that was saved")
    description_id: UUID | None = Field(None, description="Selected description resource UUID")
    description: str | None = Field(None, description="Description value that was saved")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed cohort_active flag state")
    department_ids: list[UUID] = Field(default_factory=list, description="Selected department UUIDs")
    departments: list[str] = Field(default_factory=list, description="Department values that were saved")
    simulation_ids: list[UUID] = Field(default_factory=list, description="Selected simulation UUIDs")
    simulations: list[str] = Field(default_factory=list, description="Simulation values that were saved")
    simulation_position_ids: list[UUID] = Field(default_factory=list, description="Selected simulation position UUIDs")
    simulation_positions: list[DraftSimulationPositionValue] = Field(default_factory=list, description="Simulation position values that were saved")
    simulation_availability_ids: list[UUID] = Field(default_factory=list, description="Selected simulation availability UUIDs")
    simulation_availability: list[DraftSimulationAvailabilityValue] = Field(default_factory=list, description="Simulation availability values that were saved")
    profile_ids: list[UUID] = Field(default_factory=list, description="Selected profile UUIDs")
    profiles: list[str] = Field(default_factory=list, description="Profile values that were saved")
    profile_persona_ids: list[UUID] = Field(default_factory=list, description="Selected profile persona UUIDs")
    profile_personas: list[DraftProfilePersonaValue] = Field(default_factory=list, description="Profile persona values that were saved")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource IDs retained on the draft")


class CohortDraftFormState(DraftFormState):
    """Backward-compatible alias for callers still importing the old name."""


class PatchCohortDraftApiResponse(BaseModel):
    """Response model for new-style cohort draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="Draft UUID")
    idempotency_key: UUID = Field(..., description="Idempotency key for this draft operation")
    message: str = Field(..., description="Human-readable result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


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

    file_id: UUID = Field(..., description="UUID of the files_resource holding the export CSV")
    file_name: str = Field(..., description="Suggested download file name")
    row_count: int = Field(..., description="Number of data rows in the export")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key (audit call_id). On a soft propose, echo this back with `accept` to promote/reject the staged export.")


class FileDownloadCohortApiRequest(BaseModel):
    """Request model for cohort file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadCohortApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# SQL Row Types (for internal use)
# =============================================================================
# Note: GetCohortAccessSqlParams, GetCohortAccessSqlRow, GetCohortIdsSqlParams,
# and GetCohortIdsSqlRow are now auto-generated in app/sql/types.py from the
# corresponding SQL files in app/sql/queries/cohorts/


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


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsCohortApiRequest(BaseModel):
    """Request model for cohort generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GenerationsCohortListItem(BaseModel):
    """Single generation group in the cohort generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsCohortApiResponse(BaseModel):
    """Response model for cohort generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsCohortListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemCohortApiRequest(BaseModel):
    """Request model for cohort problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemCohortApiResponse(BaseModel):
    """Response model for cohort problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadCohortApiRequest(BaseModel):
    """Request model for cohort text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadCohortApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadCohortApiRequest(BaseModel):
    """Request model for cohort call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadCohortApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
