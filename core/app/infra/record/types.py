"""Types for record artifact."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RecordRequest(BaseModel):
    """Request for record profile report — dashboard scoped to one profile."""

    target_profile_id: UUID = Field(..., description="Target profile ID to scope data")

    # Global filters
    start_date: str | None = Field(None, description="Filter start date")
    end_date: str | None = Field(None, description="Filter end date")
    cohort_ids: list[UUID] | None = Field(None, description="Cohort IDs to filter by")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation IDs to filter by")
    department_ids: list[UUID] | None = Field(None, description="Department IDs to filter by")
    simulation_filters: list[str] | None = Field(None, description="Simulation filter strings")
    actor_profile_id: UUID | None = Field(None, description="Acting user profile ID")

    # Section pickers
    rubric_ids: list[UUID] | None = Field(None, description="Rubric IDs for section picker")
    rubric_search: str | None = Field(None, description="Search string for rubrics")
    simulation_picker_ids: list[UUID] | None = Field(None, description="Simulation picker IDs")
    simulation_picker_search: str | None = Field(None, description="Search string for simulations")
    parameter_ids: list[UUID] | None = Field(None, description="Parameter IDs for section picker")
    parameter_search: str | None = Field(None, description="Search string for parameters")
    scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs for section picker")
    scenario_search: str | None = Field(None, description="Search string for scenarios")

    # History section (inline in /get for backward compat)
    history_practice: bool = Field(False, description="Filter to practice attempts only")
    history_scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs for history filter")
    history_infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")
    history_show_archived: bool = Field(False, description="Include archived attempts")
    history_sort_by: str | None = Field("date", description="History sort field")
    history_sort_order: str | None = Field("desc", description="History sort direction")
    history_page: int = Field(0, description="History pagination page number")
    history_page_size: int = Field(20, description="History items per page")
    history_simulation_search: str | None = Field(None, description="Search string for history simulations")
    history_scenario_search: str | None = Field(None, description="Search string for history scenarios")
    history_profile_search: str | None = Field(None, description="Search string for history profiles")


class ListRecordRequest(BaseModel):
    """Request for record history list endpoint (paginated attempt history)."""

    target_profile_id: UUID = Field(..., description="Target profile ID to scope data")

    # Global filters
    start_date: str | None = Field(None, description="Filter start date")
    end_date: str | None = Field(None, description="Filter end date")
    cohort_ids: list[UUID] | None = Field(None, description="Cohort IDs to filter by")
    department_ids: list[UUID] | None = Field(None, description="Department IDs to filter by")

    # History-specific
    practice: bool = Field(False, description="Filter to practice attempts only")
    scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs to filter by")
    infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")
    show_archived: bool = Field(False, description="Include archived attempts")
    sort_by: str = Field("date", description="Sort field name")
    sort_order: str = Field("desc", description="Sort direction (asc or desc)")
    page: int = Field(0, description="Pagination page number")
    page_size: int = Field(20, description="Items per page")
    simulation_search: str | None = Field(None, description="Search string for simulations")
    scenario_search: str | None = Field(None, description="Search string for scenarios")


# =============================================================================
# Export endpoint types
# =============================================================================


class ExportRecordApiResponse(BaseModel):
    """Response model for record export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsRecordApiRequest(BaseModel):
    """Request model for record generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsRecordListItem(BaseModel):
    """Single generation group in the record generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsRecordApiResponse(BaseModel):
    """Response model for record generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsRecordListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemRecordApiRequest(BaseModel):
    """Request model for record problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")


class ProblemRecordApiResponse(BaseModel):
    """Response model for record problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
