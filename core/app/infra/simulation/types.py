"""Simulation API types - handcrafted types for simulation endpoints.

These types are used for the simulation API endpoints and include
Python-computed permissions and UI flags.
"""

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import BaseResourceSection, ListFilterSection
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.simulation_drafts.types import (
    GetSimulationDraftResponse,
)

# =============================================================================
# Resource Types (handcrafted — no dependency on app.sql.types)
# =============================================================================


class SimulationNameResource(BaseModel):
    """Name resource for simulation."""

    id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class SimulationDescriptionResource(BaseModel):
    """Description resource for simulation."""

    id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class SimulationScenarioFlag(BaseModel):
    """Scenario flag (denormalized: includes flag name/description/icon/type/value)."""

    id: UUID | None = Field(None, description="UUID of the scenario flag")
    scenario_id: UUID | None = Field(None, description="UUID of the parent scenario")
    flag_id: UUID | None = Field(None, description="UUID of the flag resource")
    name: str | None = Field(None, description="Flag name")
    type: str | None = Field(None, description="Underlying flag type (e.g. 'audio_enabled')")
    value: bool | None = Field(None, description="Underlying flag boolean value")
    description: str | None = Field(None, description="Flag description text")
    icon: str | None = Field(None, description="Icon identifier for the flag")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class SimulationScenarioFlagOption(BaseModel):
    """Option row for ScenarioFlags picker — one per (scenario × flag_type × value).

    The junction row of scenario_flags_resource links (scenario_id, flag_id);
    the client needs a pre-computed cross-product so each (scenario, type)
    pair can be rendered as a switch. `flag_id` here is the underlying
    flags_resource row ID for that (type, value) pair.
    """

    scenario_id: UUID | None = Field(None, description="UUID of the parent scenario")
    flag_id: UUID | None = Field(None, description="UUID of the underlying flag resource (value-specific)")
    type: str | None = Field(None, description="Flag type")
    value: bool | None = Field(None, description="Underlying flag boolean value")
    name: str | None = Field(None, description="Flag display name")
    description: str | None = Field(None, description="Flag description text")
    icon: str | None = Field(None, description="Resolved SVG markup")


class SimulationScenarioPosition(BaseModel):
    """Scenario position."""

    id: UUID | None = Field(None, description="UUID of the scenario position")
    scenario_id: UUID | None = Field(None, description="UUID of the parent scenario")
    value: int | None = Field(None, description="Position value")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class SimulationScenarioRubric(BaseModel):
    """Scenario rubric."""

    id: UUID | None = Field(None, description="UUID of the scenario rubric")
    scenario_id: UUID | None = Field(None, description="UUID of the parent scenario")
    rubric_id: UUID | None = Field(None, description="UUID of the rubric resource")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class SimulationScenarioTimeLimit(BaseModel):
    """Scenario time limit."""

    id: UUID | None = Field(None, description="UUID of the scenario time limit")
    scenario_id: UUID | None = Field(None, description="UUID of the parent scenario")
    time_limit_seconds: int | None = Field(None, description="Time limit in seconds")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    negative: bool | None = Field(None, description="Whether the time limit is negative")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class SimulationRubric(BaseModel):
    """Rubric catalog item."""

    id: UUID | None = Field(None, description="UUID of the rubric")
    name: str | None = Field(None, description="Rubric name")
    description: str | None = Field(None, description="Rubric description text")
    standard_group_ids: list[UUID] | None = Field(None, description="Associated standard group UUIDs")


class SimulationDraftEntry(BaseModel):
    """Simulation draft entry for websocket."""

    draft_id: UUID | None = Field(None, description="UUID of the draft")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")

    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether this is an MCP draft")
    active: bool | None = Field(None, description="Whether the draft is active")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    name_ids: list[UUID] | None = Field(None, description="Selected name resource UUIDs")
    description_ids: list[UUID] | None = Field(None, description="Selected description resource UUIDs")
    flag_ids: list[UUID] | None = Field(None, description="Selected flag UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Selected department UUIDs")
    scenario_ids: list[UUID] | None = Field(None, description="Selected scenario UUIDs")
    scenario_flag_ids: list[UUID] | None = Field(None, description="Selected scenario flag UUIDs")
    scenario_position_ids: list[UUID] | None = Field(None, description="Selected scenario position UUIDs")
    scenario_rubric_ids: list[UUID] | None = Field(None, description="Selected scenario rubric UUIDs")
    scenario_time_limit_ids: list[UUID] | None = Field(None, description="Selected scenario time limit UUIDs")


class SimulationFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'simulation_active', 'practice')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SimulationDepartment(BaseModel):
    """Department for simulation."""

    department_id: UUID | None = Field(None, description="UUID of the department")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


class SimulationScenario(BaseModel):
    """Scenario for simulation."""

    scenario_id: UUID | None = Field(None, description="UUID of the scenario")
    name: str | None = Field(None, description="Scenario name")
    description: str | None = Field(None, description="Scenario description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    # Computed show_* flags (business logic in Python)
    show_problem_statement: bool | None = Field(None, description="Whether to show problem statement")
    show_objectives: bool | None = Field(None, description="Whether to show objectives")
    show_video: bool | None = Field(None, description="Whether to show video")
    show_text: bool | None = Field(None, description="Whether to show text input")
    show_audio: bool | None = Field(None, description="Whether to show audio input")
    show_copy_paste: bool | None = Field(None, description="Whether to show copy/paste")
    show_images: bool | None = Field(None, description="Whether to show images")
    show_questions: bool | None = Field(None, description="Whether to show questions")
    suggested: bool = Field(False, description="Whether this is a suggested option")
    selected: bool = Field(False, description="Whether this is currently selected")
    pending: bool = Field(False, description="Whether this selection is pending acceptance")


# =============================================================================
# Resource Bucket Types (persona-style)
# =============================================================================


class SimulationResourceBucket(BaseModel):
    """Generic resources bucket with full objects (always plural lists)."""

    names: list[SimulationNameResource] | None = Field(None, description="List of name resources")
    descriptions: list[SimulationDescriptionResource] | None = Field(None, description="List of description resources")
    flags: list[SimulationFlagResource] | None = Field(None, description="List of flag configs")
    departments: list[SimulationDepartment] | None = Field(None, description="List of department resources")
    scenarios: list[SimulationScenario] | None = Field(None, description="List of scenario resources")
    scenario_flags: list[SimulationScenarioFlag] | None = Field(None, description="List of scenario flag resources")
    scenario_positions: list[SimulationScenarioPosition] | None = Field(None, description="List of scenario position resources")
    scenario_rubrics: list[SimulationScenarioRubric] | None = Field(None, description="List of scenario rubric resources")
    scenario_time_limits: list[SimulationScenarioTimeLimit] | None = Field(None, description="List of scenario time limit resources")
    rubrics: list[SimulationRubric] | None = Field(None, description="List of rubric catalog items")


class SimulationResources(BaseModel):
    """Full resources + current selections."""

    resources: SimulationResourceBucket | None = Field(None, description="All available resources")
    current: SimulationResourceBucket | None = Field(None, description="Currently selected resources")


# =============================================================================
# Access Check Types (Query 1)
# =============================================================================


class GetSimulationAccessSqlParams(BaseModel):
    """Parameters for simulation access check query."""

    profile_id: UUID = Field(..., description="UUID of the requesting profile")
    simulation_id: UUID | None = Field(None, description="UUID of the simulation")
    draft_id: UUID | None = Field(None, description="UUID of the draft")

    def to_tuple(self) -> tuple[Any, ...]:
        return (self.profile_id, self.simulation_id, self.draft_id)


class GetSimulationAccessSqlRow(BaseModel):
    """Row returned from simulation access check query."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    simulation_exists: bool | None = Field(None, description="Whether the simulation exists")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    user_role: str | None = Field(None, description="Role of the current user")
    user_department_ids: list[UUID] | None = Field(None, description="Department UUIDs of the user")
    simulation_department_ids: list[UUID] | None = Field(None, description="Department UUIDs of the simulation")
    cohort_usage_count: int | None = Field(None, description="Number of cohorts using this simulation")


# =============================================================================
# ID Fetching Types (Query 2)
# =============================================================================


class GetSimulationIdsSqlParams(BaseModel):
    """Parameters for simulation ID fetching query."""

    profile_id: UUID = Field(..., description="UUID of the requesting profile")
    simulation_id: UUID | None = Field(None, description="UUID of the simulation")
    draft_id: UUID | None = Field(None, description="UUID of the draft")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    user_department_ids: list[UUID] | None = Field(default_factory=list, description="Department UUIDs of the user")

    def to_tuple(self) -> tuple[Any, ...]:
        return (
            self.profile_id,
            self.simulation_id,
            self.draft_id,
            self.group_id,
            self.user_department_ids,
        )


class GetSimulationIdsSqlRow(BaseModel):
    """Row returned from simulation ID fetching query."""

    # Single-select IDs
    name_id: UUID | None = Field(None, description="UUID of the selected name resource")
    description_id: UUID | None = Field(None, description="UUID of the selected description resource")

    # Multi-select IDs
    flag_ids: list[UUID] | None = Field(None, description="Selected flag UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Selected department UUIDs")
    scenario_ids: list[UUID] | None = Field(None, description="Selected scenario UUIDs")
    scenario_flag_ids: list[UUID] | None = Field(None, description="Selected scenario flag UUIDs")
    scenario_position_ids: list[UUID] | None = Field(None, description="Selected scenario position UUIDs")
    scenario_rubric_ids: list[UUID] | None = Field(None, description="Selected scenario rubric UUIDs")
    scenario_time_limit_ids: list[UUID] | None = Field(None, description="Selected scenario time limit UUIDs")

    # Candidate agents (for Python-side agent scoring)
    candidate_agents: list[dict] | None = Field(None, description="Candidate agent data for scoring")

    # Tools existence flags
    names_has_tools: bool | None = Field(None, description="Whether names resource has tools")
    descriptions_has_tools: bool | None = Field(None, description="Whether descriptions resource has tools")
    flags_has_tools: bool | None = Field(None, description="Whether flags resource has tools")
    departments_has_tools: bool | None = Field(None, description="Whether departments resource has tools")
    scenarios_has_tools: bool | None = Field(None, description="Whether scenarios resource has tools")
    scenario_flags_has_tools: bool | None = Field(None, description="Whether scenario flags resource has tools")
    scenario_positions_has_tools: bool | None = Field(None, description="Whether scenario positions resource has tools")
    scenario_rubrics_has_tools: bool | None = Field(None, description="Whether scenario rubrics resource has tools")
    scenario_time_limits_has_tools: bool | None = Field(None, description="Whether scenario time limits resource has tools")


# =============================================================================
# Scenarios Resource Types
# =============================================================================


class QGetScenariosV4Item(BaseModel):
    """Scenario item from scenarios resource query."""

    scenario_id: UUID | None = Field(None, description="UUID of the scenario")
    name: str | None = Field(None, description="Scenario name")
    description: str | None = Field(None, description="Scenario description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    # Raw _enabled flags from SQL (business logic computed in Python)
    problem_statement_enabled: bool | None = Field(None, description="Whether problem statement is enabled")
    objectives_enabled: bool | None = Field(None, description="Whether objectives are enabled")
    video_enabled: bool | None = Field(None, description="Whether video is enabled")
    images_enabled: bool | None = Field(None, description="Whether images are enabled")
    questions_enabled: bool | None = Field(None, description="Whether questions are enabled")
    # Denormalized resource IDs
    persona_ids: list[UUID] | None = Field(None, description="Associated persona UUIDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Associated parameter field UUIDs")
    document_ids: list[UUID] | None = Field(None, description="Associated document UUIDs")
    objective_ids: list[UUID] | None = Field(None, description="Associated objective UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Associated image UUIDs")
    video_ids: list[UUID] | None = Field(None, description="Associated video UUIDs")
    question_ids: list[UUID] | None = Field(None, description="Associated question UUIDs")
    option_ids: list[UUID] | None = Field(None, description="Associated option UUIDs")
    problem_statement_ids: list[UUID] | None = Field(None, description="Associated problem statement UUIDs")


class GetScenariosSqlParams(BaseModel):
    """Parameters for getting scenarios by IDs."""

    ids: list[UUID] = Field(..., description="List of scenario UUIDs to retrieve")

    def to_tuple(self) -> tuple[Any, ...]:
        return (self.ids,)


class GetScenariosSqlRow(BaseModel):
    """Row returned from scenarios get query."""

    items: list[QGetScenariosV4Item] | None = Field(None, description="List of scenario items")


class SearchScenariosSqlParams(BaseModel):
    """Parameters for searching scenarios."""

    search: str | None = Field(None, description="Search query text")
    limit_count: int | None = Field(20, description="Maximum number of results")
    offset_count: int | None = Field(0, description="Pagination offset")
    user_department_ids: list[UUID] | None = Field(None, description="Department UUIDs of the user")
    suggest_source: str | None = Field(None, description="Source context for suggestions")
    exclude_ids: list[UUID] | None = Field(None, description="Scenario UUIDs to exclude")

    def to_tuple(self) -> tuple[Any, ...]:
        return (
            self.search,
            self.limit_count,
            self.offset_count,
            self.user_department_ids,
            self.suggest_source,
            self.exclude_ids,
        )


class SearchScenariosSqlRow(BaseModel):
    """Row returned from scenarios search query."""

    items: list[QGetScenariosV4Item] | None = Field(None, description="List of scenario items")


# API Request/Response types for scenarios resource
class GetScenariosApiRequest(BaseModel):
    """Request for getting scenarios by IDs."""

    ids: list[UUID] = Field(..., description="List of scenario UUIDs to retrieve")


class GetScenariosApiResponse(BaseModel):
    """Response for getting scenarios by IDs."""

    items: list[QGetScenariosV4Item] | None = Field(None, description="List of scenario items")


class SearchScenariosApiRequest(BaseModel):
    """Request for searching scenarios."""

    search: str | None = Field(None, description="Search query text")
    limit_count: int | None = Field(20, description="Maximum number of results")
    offset_count: int | None = Field(0, description="Pagination offset")
    department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    suggest_source: str | None = Field(None, description="Source context for suggestions")
    exclude_ids: list[UUID] | None = Field(None, description="Scenario UUIDs to exclude")
    scenario: bool | None = Field(None, description="Whether to include scenario results")
    simulation: bool | None = Field(None, description="Whether to include simulation results")


class SearchScenariosApiResponse(BaseModel):
    """Response for searching scenarios."""

    items: list[QGetScenariosV4Item] | None = Field(None, description="List of scenario items")


# =============================================================================
# GET Endpoint Types (persona-style)
# =============================================================================


class SectionFilter(BaseModel):
    """Per-section filter options for GET requests."""

    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")
    parameter_ids: list[str] | None = Field(None, description="Reserved for parity with persona pattern")


class GetSimulationApiRequest(BaseModel):
    """Request model for get simulation endpoint."""

    id: UUID | None = Field(None, description="UUID of the simulation to retrieve")
    simulation_id: UUID | None = Field(None, description="Legacy alias for the simulation UUID")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load instead of published state")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    flags: SectionFilter | None = Field(None, description="Filter options for flags section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    scenarios: SectionFilter | None = Field(None, description="Filter options for scenarios section")
    scenario_flags: SectionFilter | None = Field(None, description="Filter options for scenario flags section")
    scenario_positions: SectionFilter | None = Field(None, description="Filter options for scenario positions section")
    scenario_rubrics: SectionFilter | None = Field(None, description="Filter options for scenario rubrics section")
    scenario_time_limits: SectionFilter | None = Field(None, description="Filter options for scenario time limits section")
    filter_scenario_ids: list[UUID] | None = Field(None, description="Legacy scenario ID filter for nested scenario resources")
    scenario_search: str | None = Field(None, description="Legacy search text for scenarios")
    scenario_show_selected: bool | None = Field(None, description="Legacy selected-only filter for scenarios")


class GetSimulationApiResponse(BaseModel):
    """Response model for get simulation endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    simulation_exists: bool | None = Field(None, description="Whether the simulation exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason the simulation is disabled")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )

    show_ai_generate: bool | None = Field(None, description="Whether AI generation is available")
    basic_show_ai_generate: bool | None = Field(None, description="Legacy basic-step AI generate flag")

    names: list[SimulationNameResource] | None = Field(None, description="Name resources with selected/suggested flags")
    descriptions: list[SimulationDescriptionResource] | None = Field(None, description="Description resources with selected/suggested flags")
    flags: list[SimulationFlagResource] | None = Field(None, description="Flag configs with selected/suggested flags")
    departments: list[SimulationDepartment] | None = Field(None, description="Department resources with selected/suggested flags")
    scenarios: list[SimulationScenario] | None = Field(None, description="Scenario resources with selected/suggested flags")
    scenario_flags: list[SimulationScenarioFlag] | None = Field(None, description="Scenario flag resources with selected/suggested flags")
    scenario_flag_options: list[SimulationScenarioFlagOption] | None = Field(None, description="Cross-product of (scenario × flag type × value) for the ScenarioFlags picker")
    scenario_positions: list[SimulationScenarioPosition] | None = Field(None, description="Scenario position resources with selected/suggested flags")
    scenario_rubrics: list[SimulationScenarioRubric] | None = Field(None, description="Scenario rubric resources with selected/suggested flags")
    scenario_time_limits: list[SimulationScenarioTimeLimit] | None = Field(None, description="Scenario time limit resources with selected/suggested flags")
    rubrics: list[SimulationRubric] | None = Field(None, description="Available rubric catalog items")


class GetSimulationDraftsApiRequest(BaseModel):
    """Request model for the simulation drafts list endpoint.

    Mirrors ``GenerationsSimulationApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GetSimulationDraftsApiResponse(BaseModel):
    """Response model for simulation drafts list endpoint."""

    entries: list[GetSimulationDraftResponse] | None = Field(None, description="List of simulation draft entries")


# =============================================================================
# LIST Endpoint Types
# =============================================================================


class ListSimulationApiSimulation(BaseModel):
    """Simulation item in list response with Python-computed permissions."""

    simulation_id: UUID | None = Field(None, description="UUID of the simulation")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Simulation description text")
    department_ids: list[str] | None = Field(None, description="Associated department UUIDs")
    flag_ids: list[UUID] | None = Field(None, description="Currently selected flag option UUIDs")
    is_inactive: bool | None = Field(None, description="Whether the simulation is inactive (derived from simulation_active flag)")
    is_practice: bool | None = Field(None, description="Whether this is a practice simulation (derived from practice flag)")
    practice_simulation: bool | None = Field(None, description="Legacy alias for is_practice — prefer is_practice")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether this is an MCP simulation")
    scenario_ids: list[str] | None = Field(None, description="Associated scenario UUIDs")
    num_cohorts: int | None = Field(None, description="Total number of cohorts")
    cohort_usage_count: int | None = Field(None, description="Number of cohorts using this simulation")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    cohort_ids: list[str] | None = Field(None, description="Associated cohort UUIDs")
    # Soft-call ledger snapshot — set when this simulation has a pending op
    # in ``soft_calls_mv``. Client renders ghost/pending styling when set.
    pending_status: str | None = Field(None, description="Latest soft_calls_mv status: 'pending' / 'accepted' / 'rejected'")
    pending_operation: str | None = Field(None, description="Operation type ('create'|'update'|'delete'|'duplicate') of the pending op")
    pending_call_id: UUID | None = Field(None, description="call_id (idempotency key for ack) of the pending op")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")


class ListSimulationApiPersona(BaseModel):
    """Persona in list response (minimal: only for color dot rendering)."""

    persona_id: str | None = Field(None, description="UUID of the persona")
    color: str | None = Field(None, description="Display color for the persona")


class ListSimulationApiScenario(BaseModel):
    """Scenario in list response (minimal: only for color dot rendering)."""

    scenario_id: UUID | None = Field(None, description="UUID of the scenario")
    name: str | None = Field(None, description="Scenario name")
    persona_ids: list[str] | None = Field(None, description="Associated persona UUIDs")
    persona_mapping: list[ListSimulationApiPersona] | None = Field(None, description="Persona color mapping for rendering")


class ListSimulationApiResponse(BaseModel):
    """Response for listing simulations."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    simulations: list[ListSimulationApiSimulation] | None = Field(None, description="List of simulation items")
    scenarios: list[ListSimulationApiScenario] | None = Field(None, description="List of scenario items")
    scenario_filter: "ListFilterSection | None" = Field(None, description="Filter options for scenarios")
    cohort_filter: "ListFilterSection | None" = Field(None, description="Filter options for cohorts")
    department_filter: "ListFilterSection | None" = Field(None, description="Filter options for departments")
    flag_filter: "ListFilterSection | None" = Field(None, description="Filter options for flags")
    total_count: int | None = Field(None, description="Total number of matching records")


# =============================================================================
# Resource Action Types (for tool call tracking)
# =============================================================================


# =============================================================================
# Shared Save/Create/Update Types
# =============================================================================


class SimulationFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


class SimulationResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    simulation_id: UUID | None = Field(None, description="UUID of the affected simulation")
    message: str = Field(..., description="Human-readable result message")
    errors: list[SimulationFieldError] | None = Field(None, description="List of per-field errors")


# =============================================================================
# Create Endpoint Types
# =============================================================================


class CreateSimulationItem(ScopedItem):
    """Single simulation item for create — no simulation_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "department_ids": "departments",
        "departments": "departments",
        "scenario_ids": "scenarios",
        "scenarios": "scenarios",
        "scenario_flag_ids": "scenario_flags",
        "scenario_position_ids": "scenario_positions",
        "scenario_rubric_ids": "scenario_rubrics",
        "scenario_time_limit_ids": "scenario_time_limits",
        "flag_ids": "flags",
    }

    id: UUID | None = Field(None, description="Client-provided UUID for the simulation")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    # Canonical flag list — server derives semantics by flag type/value
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    # Multi-select IDs
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario UUIDs")
    scenario_flag_ids: list[UUID] | None = Field(None, description="Associated scenario flag UUIDs")
    scenario_position_ids: list[UUID] | None = Field(None, description="Associated scenario position UUIDs")
    scenario_rubric_ids: list[UUID] | None = Field(None, description="Associated scenario rubric UUIDs")
    scenario_time_limit_ids: list[UUID] | None = Field(None, description="Associated scenario time limit UUIDs")
    # Value-based fields for CSV import (match-by-name resolution)
    departments: list[str] | None = Field(None, description="Department names for matching")
    scenarios: list[str] | None = Field(None, description="Scenario names for matching")


class CreateSimulationApiRequest(BaseModel):
    """Request model for bulk create simulation endpoint."""

    simulations: list[CreateSimulationItem] = Field(..., description="List of simulations to create")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateSimulationApiResponse(BaseModel):
    """Response model for bulk create simulation endpoint."""

    results: list[SimulationResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# Update Endpoint Types
# =============================================================================


class UpdateSimulationItem(ScopedItem):
    """Single simulation item for update — simulation_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateSimulationItem.RESOURCE_TYPE_MAP

    id: UUID = Field(..., description="UUID of the simulation to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    # Canonical flag list — server derives semantics by flag type/value
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    # Multi-select IDs
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario UUIDs")
    scenario_flag_ids: list[UUID] | None = Field(None, description="Associated scenario flag UUIDs")
    scenario_position_ids: list[UUID] | None = Field(None, description="Associated scenario position UUIDs")
    scenario_rubric_ids: list[UUID] | None = Field(None, description="Associated scenario rubric UUIDs")
    scenario_time_limit_ids: list[UUID] | None = Field(None, description="Associated scenario time limit UUIDs")
    # Value-based fields for CSV import (match-by-name resolution)
    departments: list[str] | None = Field(None, description="Department names for matching")
    scenarios: list[str] | None = Field(None, description="Scenario names for matching")


class UpdateSimulationPatch(UpdateSimulationItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateSimulationItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved simulation id per matched row",
    )


class UpdateSimulationApiRequest(BaseModel):
    """Request model for bulk update simulation endpoint.

    Three body shapes:
      - First call (explicit): ``simulations`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/simulation/search`` accepts plus a single shared ``patch``
        that every matched row receives. The impl resolves matching
        ids, subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    simulations: list[UpdateSimulationItem] | None = Field(
        None, description="List of simulations to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteSimulationApiRequest;
    # ``patch`` is the shared change set applied to every matched row.
    # ``patch.id`` is ignored — each resolved id is stamped onto a
    # clone before the per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every simulation matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateSimulationPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    filter_scenario_ids: list[UUID] | None = Field(None, description="Filter by scenario UUIDs")
    filter_cohort_ids: list[UUID] | None = Field(None, description="Filter by cohort UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    scenario_search: str | None = Field(None, description="Search text for scenario facet (no-op for row filtering)")
    cohort_search: str | None = Field(None, description="Search text for cohort facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateSimulationApiResponse(BaseModel):
    """Response model for bulk update simulation endpoint."""

    results: list[SimulationResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveSimulationFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


# =============================================================================
# EXPORT Endpoint Types
# =============================================================================


class ExportSimulationApiRequest(BaseModel):
    """Request model for export simulation endpoint."""

    simulation_id: UUID | None = Field(None, description="UUID of the simulation to export")

    search: str | None = Field(None, description="Search query text")
    filter_scenario_ids: list[str] | None = Field(None, description="Filter by scenario UUIDs")
    filter_cohort_ids: list[str] | None = Field(None, description="Filter by cohort UUIDs")
    filter_department_ids: list[str] | None = Field(None, description="Filter by department UUIDs")


class ExportSimulationApiResponse(BaseModel):
    """Response model for export simulation endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Total number of exported rows")


# =============================================================================
# DELETE Endpoint Types
# =============================================================================


class DeleteSimulationApiRequest(BaseModel):
    """Request model for bulk delete simulation endpoint.

    Three body shapes:
      - First call (explicit): ``simulation_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/simulation/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    simulation_ids: list[UUID] | None = Field(
        None, description="UUIDs of simulations to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchSimulationApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every simulation matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /simulation/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``simulation_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    filter_scenario_ids: list[UUID] | None = Field(None, description="Filter by scenario UUIDs")
    filter_cohort_ids: list[UUID] | None = Field(None, description="Filter by cohort UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    scenario_search: str | None = Field(None, description="Search text for scenario facet (no-op for row filtering)")
    cohort_search: str | None = Field(None, description="Search text for cohort facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool = Field(True, description="Accept (confirm deletion) or reject (restore). Only meaningful with idempotency_key")


class DeleteSimulationResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    simulation_id: UUID = Field(..., description="UUID of the deleted simulation")
    message: str = Field(..., description="Human-readable result message")


class DeleteSimulationApiResponse(BaseModel):
    """Response model for bulk delete simulation endpoint."""

    results: list[DeleteSimulationResult] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# DUPLICATE Endpoint Types
# =============================================================================


class DuplicateSimulationApiRequest(BaseModel):
    """Request for duplicating a simulation."""

    simulation_id: UUID = Field(..., description="UUID of the simulation to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateSimulationApiResponse(BaseModel):
    """Response for duplicating a simulation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    simulation_id: UUID = Field(..., description="UUID of the duplicated simulation")
    message: str = Field(..., description="Human-readable result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# DRAFT Endpoint Types
# =============================================================================


class DraftScenarioFlagValue(BaseModel):
    """Value for creating a scenario_flag resource via draft."""

    scenario_id: UUID = Field(..., description="UUID of the parent scenario")
    flag_id: UUID = Field(..., description="UUID of the flag resource")


class DraftScenarioFlagDenormValue(BaseModel):
    """Denormalized scenario_flag value — resolved server-side to (scenario_id, flag_id).

    Given (scenario_id, type, value), the server looks up the flags_resource
    row matching (type, value) and upserts a scenario_flags_resource row for
    (scenario_id, flag_id).
    """

    scenario_id: UUID = Field(..., description="UUID of the parent scenario")
    type: str = Field(..., description="Flag type in flags_resource")
    value: bool = Field(..., description="Desired boolean value for this flag type")


class DraftScenarioPositionValue(BaseModel):
    """Value for creating a scenario_position resource via draft."""

    scenario_id: UUID = Field(..., description="UUID of the parent scenario")
    value: int = Field(..., description="Position value")


class DraftScenarioRubricValue(BaseModel):
    """Value for creating a scenario_rubric resource via draft."""

    scenario_id: UUID = Field(..., description="UUID of the parent scenario")
    rubric_id: UUID = Field(..., description="UUID of the rubric resource")


class DraftScenarioTimeLimitValue(BaseModel):
    """Value for creating a scenario_time_limit resource via draft."""

    scenario_id: UUID = Field(..., description="UUID of the parent scenario")
    time_limit_seconds: int = Field(..., description="Time limit in seconds")
    negative: bool = Field(False, description="Whether the time limit is negative")


class PatchSimulationDraftApiRequest(ScopedItem):
    """Request model for new-style simulation draft endpoint.

    Dual-mode for creatable resources:
      - Single-select: name/name_id, description/description_id
      - Multi-select compound: scenario_flags, scenario_positions,
        scenario_rubrics, scenario_time_limits (values create resources,
        created IDs merged with existing IDs)
    ID-only for non-creatable resources:
      - flag_ids, department_ids, scenario_ids

    Client always sends full state (append-only — each write is a new snapshot).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "active": "flags",
        "practice": "flags",
        "department_ids": "departments",
        "scenario_ids": "scenarios",
        "scenario_flag_ids": "scenario_flags",
        "scenario_flags": "scenario_flags",
        "scenario_position_ids": "scenario_positions",
        "scenario_positions": "scenario_positions",
        "scenario_rubric_ids": "scenario_rubrics",
        "scenario_rubrics": "scenario_rubrics",
        "scenario_time_limit_ids": "scenario_time_limits",
        "scenario_time_limits": "scenario_time_limits",
    }

    draft_id: UUID | None = Field(None, description="Existing draft UUID to patch")
    input_draft_id: UUID | None = Field(None, description="Legacy alias for the input draft UUID")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    # Denormalized booleans — resolved server-side to flag_ids entries via (type, value) lookup.
    active: bool | None = Field(None, description="Denormalized simulation_active flag state")
    practice: bool | None = Field(None, description="Denormalized practice flag state")
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario UUIDs")

    # Creatable multi-select compound — values create resources, IDs merged
    scenario_flag_ids: list[UUID] | None = Field(None, description="Existing scenario flag UUIDs")
    scenario_flags: list[DraftScenarioFlagValue] | None = Field(None, description="Scenario flag values to create")
    scenario_flag_values: list[DraftScenarioFlagDenormValue] | None = Field(None, description="Denormalized (scenario_id, type, value) entries resolved server-side to scenario_flags_resource rows")
    scenario_position_ids: list[UUID] | None = Field(None, description="Existing scenario position UUIDs")
    scenario_positions: list[DraftScenarioPositionValue] | None = Field(None, description="Scenario position values to create")
    scenario_rubric_ids: list[UUID] | None = Field(None, description="Existing scenario rubric UUIDs")
    scenario_rubrics: list[DraftScenarioRubricValue] | None = Field(None, description="Scenario rubric values to create")
    scenario_time_limit_ids: list[UUID] | None = Field(None, description="Existing scenario time limit UUIDs")
    scenario_time_limits: list[DraftScenarioTimeLimitValue] | None = Field(None, description="Scenario time limit values to create")
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep as pending where supported by the tool layer")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant draft")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DraftFormState(BaseModel):
    """Full form state after draft patch — server is source of truth.

    Client replaces its local form state with this after every successful patch.
    """

    name_id: UUID | None = Field(None, description="UUID of the selected name resource")
    name: str | None = Field(None, description="Saved name value")
    description_id: UUID | None = Field(None, description="UUID of the selected description resource")
    description: str | None = Field(None, description="Saved description value")
    flag_ids: list[UUID] = Field([], description="Selected flag UUIDs")
    active: bool | None = Field(None, description="Echoed simulation_active flag state")
    practice: bool | None = Field(None, description="Echoed practice flag state")
    department_ids: list[UUID] = Field([], description="Selected department UUIDs")
    scenario_ids: list[UUID] = Field([], description="Selected scenario UUIDs")
    scenario_flag_ids: list[UUID] = Field([], description="Selected scenario flag UUIDs")
    scenario_flag_values: list[DraftScenarioFlagDenormValue] = Field([], description="Echoed denormalized (scenario_id, type, value) entries")
    scenario_position_ids: list[UUID] = Field([], description="Selected scenario position UUIDs")
    scenario_rubric_ids: list[UUID] = Field([], description="Selected scenario rubric UUIDs")
    scenario_time_limit_ids: list[UUID] = Field([], description="Selected scenario time limit UUIDs")
    pending_ids: list[UUID] = Field([], description="Pending resource UUIDs (empty until tool-layer support exists)")


SimulationDraftFormState = DraftFormState


class PatchSimulationDraftApiResponse(BaseModel):
    """Response model for new-style simulation draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    idempotency_key: UUID = Field(..., description="Idempotency key for this draft operation")
    message: str = Field(..., description="Human-readable result message")
    form_state: DraftFormState = Field(..., description="Server-authoritative form state")


# =============================================================================
# SQL Row Types (for internal use)
# =============================================================================


class ListSimulationSqlSimulation(BaseModel):
    """Raw simulation from SQL — permissions computed in Python."""

    simulation_id: UUID | None = Field(None, description="UUID of the simulation")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Simulation description text")
    department_ids: list[str] | None = Field(None, description="Associated department UUIDs")
    is_inactive: bool | None = Field(None, description="Whether the simulation is inactive")
    practice_simulation: bool | None = Field(None, description="Whether this is a practice simulation")
    scenario_ids: list[str] | None = Field(None, description="Associated scenario UUIDs")
    num_cohorts: int | None = Field(None, description="Total number of cohorts")
    cohort_usage_count: int | None = Field(None, description="Number of cohorts using this simulation")
    cohort_ids: list[str] | None = Field(None, description="Associated cohort UUIDs")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether this is an MCP simulation")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")


class ListSimulationSqlRow(BaseModel):
    """Raw SQL row for list simulations."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    simulations: list[ListSimulationSqlSimulation] | None = Field(None, description="List of raw simulation records")
    scenario_options: list[dict] | None = Field(None, description="Scenario filter option data")
    cohort_options: list[dict] | None = Field(None, description="Cohort filter option data")
    department_options: list[dict] | None = Field(None, description="Department filter option data")
    total_count: int | None = Field(None, description="Total number of matching records")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsSimulationApiRequest(BaseModel):
    """Request model for simulation generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsSimulationListItem(BaseModel):
    """Single generation group in the simulation generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsSimulationApiResponse(BaseModel):
    """Response model for simulation generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsSimulationListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemSimulationApiRequest(BaseModel):
    """Request model for simulation problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemSimulationApiResponse(BaseModel):
    """Response model for simulation problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadSimulationApiRequest(BaseModel):
    """Request model for simulation text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadSimulationApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadSimulationApiRequest(BaseModel):
    """Request model for simulation call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadSimulationApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
