"""Types for home artifact endpoint."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.auth.types import AnalyticsFacets
from app.infra.chat.types import (
    ChatSimulationOperational,
    RubricMapping,
    StandardGroupMapping,
    StandardMapping,
)
from app.infra.v5_types import HistoryResponse

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

    pass


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
