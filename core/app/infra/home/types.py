"""Types for home artifact endpoint."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import HistoryResponse
from app.infra.attempt.chat.types import (
    ChatSimulationOperational,
    RubricMapping,
    StandardGroupMapping,
    StandardMapping,
)
from app.infra.auth.types import AnalyticsFacets

# =============================================================================
# Export Types
# =============================================================================


class ExportHomeApiResponse(BaseModel):
    """Response model for home certificate export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# GET endpoint types
# =============================================================================


class GetHomeRequest(BaseModel):
    """Request for home get endpoint — simulation cards only."""

    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GetHomeResponse(BaseModel):
    """Client-facing API response for home get (operational).

    Returns simulations user can take, scoped by their cohorts.
    Includes inline analytics facets for SSR filter rendering.
    """

    actor_name: str | None = Field(None, description="Current user display name")
    items: list[ChatSimulationOperational] | None = Field(None, description="Available simulation cards")
    rubrics: list[RubricMapping] | None = Field(None, description="Rubric mapping data")
    standard_groups: list[StandardGroupMapping] | None = Field(None, description="Standard group mapping data")
    standards: list[StandardMapping] | None = Field(None, description="Standard mapping data")
    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")


# =============================================================================
# LIST endpoint types (paginated history)
# =============================================================================


class ListHomeRequest(BaseModel):
    """Request for home list endpoint — paginated attempt history."""

    sort_by: str | None = Field("date", description="Sort field name")
    sort_order: str | None = Field("desc", description="Sort direction (asc or desc)")
    page: int = Field(0, description="Pagination page number")
    page_size: int = Field(20, description="Items per page")
    simulation_search: str | None = Field(None, description="Search string for simulations")
    scenario_search: str | None = Field(None, description="Search string for scenarios")
    scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs to filter by")
    infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")


class ListHomeResponse(HistoryResponse):
    """Client-facing API response for home list (paginated history)."""

    pass


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsHomeApiRequest(BaseModel):
    """Request model for home generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsHomeListItem(BaseModel):
    """Single generation group in the home generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsHomeApiResponse(BaseModel):
    """Response model for home generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsHomeListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemHomeApiRequest(BaseModel):
    """Request model for home problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")


class ProblemHomeApiResponse(BaseModel):
    """Response model for home problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
