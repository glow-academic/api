"""Simulation API types - handcrafted types for simulation endpoints.

These types are used for the simulation API endpoints and include
Python-computed permissions and UI flags.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.simulation.create import CreateSimulationItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
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


class SimulationDescriptionResource(BaseModel):
    """Description resource for simulation."""

    id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class SimulationScenarioFlag(BaseModel):
    """Scenario flag (denormalized: includes flag name/description/icon)."""

    id: UUID | None = Field(None, description="UUID of the scenario flag")
    scenario_id: UUID | None = Field(None, description="UUID of the parent scenario")
    flag_id: UUID | None = Field(None, description="UUID of the flag resource")
    name: str | None = Field(None, description="Flag name")
    description: str | None = Field(None, description="Flag description text")
    icon: str | None = Field(None, description="Icon identifier for the flag")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class SimulationScenarioPosition(BaseModel):
    """Scenario position."""

    id: UUID | None = Field(None, description="UUID of the scenario position")
    scenario_id: UUID | None = Field(None, description="UUID of the parent scenario")
    value: int | None = Field(None, description="Position value")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class SimulationScenarioRubric(BaseModel):
    """Scenario rubric."""

    id: UUID | None = Field(None, description="UUID of the scenario rubric")
    scenario_id: UUID | None = Field(None, description="UUID of the parent scenario")
    rubric_id: UUID | None = Field(None, description="UUID of the rubric resource")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class SimulationScenarioTimeLimit(BaseModel):
    """Scenario time limit."""

    id: UUID | None = Field(None, description="UUID of the scenario time limit")
    scenario_id: UUID | None = Field(None, description="UUID of the parent scenario")
    time_limit_seconds: int | None = Field(None, description="Time limit in seconds")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    negative: bool | None = Field(None, description="Whether the time limit is negative")


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
    version: int | None = Field(None, description="Draft version number")
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


class SimulationFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag config key identifier")
    label: str = Field(..., description="Display label for the flag")
    description: str | None = Field(None, description="Flag description text")
    icon_id: str | None = Field(None, description="UUID of the selected icon resource")
    flag_option_id: UUID | None = Field(None, description="UUID of the flag option")
    show: bool = Field(True, description="Whether to show this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class SimulationDepartment(BaseModel):
    """Department for simulation."""

    department_id: UUID | None = Field(None, description="UUID of the department")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


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


# =============================================================================
# Resource Bucket Types (persona-style)
# =============================================================================


class SimulationResourceBucket(BaseModel):
    """Generic resources bucket with full objects (always plural lists)."""

    names: list[SimulationNameResource] | None = Field(None, description="List of name resources")
    descriptions: list[SimulationDescriptionResource] | None = Field(None, description="List of description resources")
    flags: list[SimulationFlagConfig] | None = Field(None, description="List of flag configs")
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
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    user_role: str | None = Field(None, description="Role of the current user")
    user_department_ids: list[UUID] | None = Field(None, description="Department UUIDs of the user")
    simulation_department_ids: list[UUID] | None = Field(None, description="Department UUIDs of the simulation")
    cohort_usage_count: int | None = Field(None, description="Number of cohorts using this simulation")
    effective_draft_version: int | None = Field(None, description="Effective draft version after resolution")


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


class GetSimulationApiRequest(BaseModel):
    """Request for getting a single simulation."""

    simulation_id: UUID | None = Field(None, description="UUID of the simulation to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to retrieve")
    scenario_search: str | None = Field(None, description="Search text to filter scenarios")
    filter_scenario_ids: list[UUID] | None = Field(None, description="Filter by scenario UUIDs")


class SimulationNameSection(BaseResourceSection):
    resource: SimulationNameResource | None = Field(None, description="Currently selected name resource")
    resources: list[SimulationNameResource] | None = Field(None, description="Available name resources")


class SimulationDescriptionSection(BaseResourceSection):
    resource: SimulationDescriptionResource | None = Field(None, description="Currently selected description resource")
    resources: list[SimulationDescriptionResource] | None = Field(None, description="Available description resources")


class SimulationFlagSection(BaseResourceSection):
    current: list[SimulationFlagConfig] | None = Field(None, description="Currently selected flags")
    resources: list[SimulationFlagConfig] | None = Field(None, description="Available flag configs")


class SimulationDepartmentSection(BaseResourceSection):
    current: list[SimulationDepartment] | None = Field(None, description="Currently selected departments")
    resources: list[SimulationDepartment] | None = Field(None, description="Available departments")


class SimulationScenarioSection(BaseResourceSection):
    current: list[SimulationScenario] | None = Field(None, description="Currently selected scenarios")
    resources: list[SimulationScenario] | None = Field(None, description="Available scenarios")


class SimulationScenarioFlagSection(BaseResourceSection):
    current: list[SimulationScenarioFlag] | None = Field(None, description="Currently selected scenario flags")
    resources: list[SimulationScenarioFlag] | None = Field(None, description="Available scenario flags")


class SimulationScenarioPositionSection(BaseResourceSection):
    current: list[SimulationScenarioPosition] | None = Field(None, description="Currently selected scenario positions")
    resources: list[SimulationScenarioPosition] | None = Field(None, description="Available scenario positions")


class SimulationScenarioRubricSection(BaseResourceSection):
    current: list[SimulationScenarioRubric] | None = Field(None, description="Currently selected scenario rubrics")
    resources: list[SimulationScenarioRubric] | None = Field(None, description="Available scenario rubrics")


class SimulationScenarioTimeLimitSection(BaseResourceSection):
    current: list[SimulationScenarioTimeLimit] | None = Field(None, description="Currently selected scenario time limits")
    resources: list[SimulationScenarioTimeLimit] | None = Field(None, description="Available scenario time limits")


class GetSimulationApiResponse(BaseModel):
    """Section-first response for simulation editor."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    simulation_exists: bool | None = Field(None, description="Whether the simulation exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason the simulation is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="UUID of the owning group")

    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")

    names: SimulationNameSection | None = Field(None, description="Name section data")
    descriptions: SimulationDescriptionSection | None = Field(None, description="Description section data")
    flags: SimulationFlagSection | None = Field(None, description="Flag section data")
    departments: SimulationDepartmentSection | None = Field(None, description="Department section data")
    scenarios: SimulationScenarioSection | None = Field(None, description="Scenario section data")
    scenario_flags: SimulationScenarioFlagSection | None = Field(None, description="Scenario flag section data")
    scenario_positions: SimulationScenarioPositionSection | None = Field(None, description="Scenario position section data")
    scenario_rubrics: SimulationScenarioRubricSection | None = Field(None, description="Scenario rubric section data")
    scenario_time_limits: SimulationScenarioTimeLimitSection | None = Field(None, description="Scenario time limit section data")
    rubrics: list[SimulationRubric] | None = Field(None, description="Available rubric catalog items")


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
    is_inactive: bool | None = Field(None, description="Whether the simulation is inactive")
    practice_simulation: bool | None = Field(None, description="Whether this is a practice simulation")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether this is an MCP simulation")
    scenario_ids: list[str] | None = Field(None, description="Associated scenario UUIDs")
    num_cohorts: int | None = Field(None, description="Total number of cohorts")
    cohort_usage_count: int | None = Field(None, description="Number of cohorts using this simulation")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    cohort_ids: list[str] | None = Field(None, description="Associated cohort UUIDs")
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


class CreateSimulationApiRequest(BaseModel):
    """Request model for bulk create simulation endpoint."""

    simulations: list[CreateSimulationItem] = Field(..., description="List of simulations to create")


class CreateSimulationApiResponse(BaseModel):
    """Response model for bulk create simulation endpoint."""

    results: list[SimulationResultItem] = Field(..., description="List of operation results")


# =============================================================================
# Update Endpoint Types
# =============================================================================


class UpdateSimulationItem(BaseModel):
    """Single simulation item for update — simulation_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    simulation_id: UUID = Field(..., description="UUID of the simulation to update")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    # Multi-select IDs
    flag_ids: list[UUID] | None = Field(None, description="Associated flag UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario UUIDs")
    scenario_flag_ids: list[UUID] | None = Field(None, description="Associated scenario flag UUIDs")
    scenario_position_ids: list[UUID] | None = Field(None, description="Associated scenario position UUIDs")
    scenario_rubric_ids: list[UUID] | None = Field(None, description="Associated scenario rubric UUIDs")
    scenario_time_limit_ids: list[UUID] | None = Field(None, description="Associated scenario time limit UUIDs")
    # Value-based fields for CSV import (match-by-name resolution)
    is_inactive: bool | None = Field(None, description="Whether the simulation is inactive")
    is_practice: bool | None = Field(None, description="Whether this is a practice simulation")
    departments: list[str] | None = Field(None, description="Department names for matching")
    scenarios: list[str] | None = Field(None, description="Scenario names for matching")


class UpdateSimulationApiRequest(BaseModel):
    """Request model for bulk update simulation endpoint."""

    simulations: list[UpdateSimulationItem] = Field(..., description="List of simulations to update")


class UpdateSimulationApiResponse(BaseModel):
    """Response model for bulk update simulation endpoint."""

    results: list[SimulationResultItem] = Field(..., description="List of operation results")


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
    """Request model for bulk delete simulation endpoint."""

    simulation_ids: list[UUID] = Field(..., description="UUIDs of simulations to delete")


class DeleteSimulationResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    simulation_id: UUID = Field(..., description="UUID of the deleted simulation")
    message: str = Field(..., description="Human-readable result message")


class DeleteSimulationApiResponse(BaseModel):
    """Response model for bulk delete simulation endpoint."""

    results: list[DeleteSimulationResult] = Field(..., description="List of operation results")


# =============================================================================
# DUPLICATE Endpoint Types
# =============================================================================


class DuplicateSimulationApiRequest(BaseModel):
    """Request for duplicating a simulation."""

    simulation_id: UUID = Field(..., description="UUID of the simulation to duplicate")


class DuplicateSimulationApiResponse(BaseModel):
    """Response for duplicating a simulation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    simulation_id: UUID = Field(..., description="UUID of the duplicated simulation")
    message: str = Field(..., description="Human-readable result message")


# =============================================================================
# DRAFT Endpoint Types
# =============================================================================


class DraftScenarioFlagValue(BaseModel):
    """Value for creating a scenario_flag resource via draft."""

    scenario_id: UUID = Field(..., description="UUID of the parent scenario")
    flag_id: UUID = Field(..., description="UUID of the flag resource")


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


class PatchSimulationDraftApiRequest(BaseModel):
    """Request model for new-style simulation draft endpoint.

    Dual-mode for creatable resources:
      - Single-select: name/name_id, description/description_id
      - Multi-select compound: scenario_flags, scenario_positions,
        scenario_rubrics, scenario_time_limits (values create resources,
        created IDs merged with existing IDs)
    ID-only for non-creatable resources:
      - flag_ids, department_ids, scenario_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="UUID of the input draft")
    expected_version: int = Field(0, description="Expected draft version for optimistic lock")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Associated flag UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario UUIDs")

    # Creatable multi-select compound — values create resources, IDs merged
    scenario_flag_ids: list[UUID] | None = Field(None, description="Existing scenario flag UUIDs")
    scenario_flags: list[DraftScenarioFlagValue] | None = Field(None, description="Scenario flag values to create")
    scenario_position_ids: list[UUID] | None = Field(None, description="Existing scenario position UUIDs")
    scenario_positions: list[DraftScenarioPositionValue] | None = Field(None, description="Scenario position values to create")
    scenario_rubric_ids: list[UUID] | None = Field(None, description="Existing scenario rubric UUIDs")
    scenario_rubrics: list[DraftScenarioRubricValue] | None = Field(None, description="Scenario rubric values to create")
    scenario_time_limit_ids: list[UUID] | None = Field(None, description="Existing scenario time limit UUIDs")
    scenario_time_limits: list[DraftScenarioTimeLimitValue] | None = Field(None, description="Scenario time limit values to create")


class SimulationDraftFormState(BaseModel):
    """Full form state after draft patch — server is source of truth.

    Client replaces its local form state with this after every successful patch.
    """

    name_id: UUID | None = Field(None, description="UUID of the selected name resource")
    description_id: UUID | None = Field(None, description="UUID of the selected description resource")
    flag_ids: list[UUID] = Field([], description="Selected flag UUIDs")
    department_ids: list[UUID] = Field([], description="Selected department UUIDs")
    scenario_ids: list[UUID] = Field([], description="Selected scenario UUIDs")
    scenario_flag_ids: list[UUID] = Field([], description="Selected scenario flag UUIDs")
    scenario_position_ids: list[UUID] = Field([], description="Selected scenario position UUIDs")
    scenario_rubric_ids: list[UUID] = Field([], description="Selected scenario rubric UUIDs")
    scenario_time_limit_ids: list[UUID] = Field([], description="Selected scenario time limit UUIDs")


class PatchSimulationDraftApiResponse(BaseModel):
    """Response model for new-style simulation draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    new_version: int = Field(..., description="New draft version number")
    message: str = Field(..., description="Human-readable result message")
    form_state: SimulationDraftFormState | None = Field(None, description="Server-authoritative form state")


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
