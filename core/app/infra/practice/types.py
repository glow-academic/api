"""Types for practice artifact endpoint."""

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


class ExportPracticeApiResponse(BaseModel):
    """Response model for practice export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# GET endpoint types
# =============================================================================


class GetPracticeRequest(BaseModel):
    """Request for practice get endpoint — simulation cards only."""

    pass


class GetPracticeResponse(BaseModel):
    """Client-facing API response for practice get (operational).

    Returns practice simulations user can take, scoped by their cohorts.
    Includes inline analytics facets for SSR filter rendering.
    """

    actor_name: str | None = Field(None, description="Current user display name")
    items: list[ChatSimulationOperational] | None = Field(None, description="Available practice simulation cards")
    rubrics: list[RubricMapping] | None = Field(None, description="Rubric mapping data")
    standard_groups: list[StandardGroupMapping] | None = Field(None, description="Standard group mapping data")
    standards: list[StandardMapping] | None = Field(None, description="Standard mapping data")
    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")


# =============================================================================
# LIST endpoint types (paginated history)
# =============================================================================


class ListPracticeRequest(BaseModel):
    """Request for practice list endpoint — paginated attempt history."""

    sort_by: str | None = Field("date", description="Sort field name")
    sort_order: str | None = Field("desc", description="Sort direction (asc or desc)")
    page: int = Field(0, description="Pagination page number")
    page_size: int = Field(20, description="Items per page")
    simulation_search: str | None = Field(None, description="Search string for simulations")
    scenario_search: str | None = Field(None, description="Search string for scenarios")
    show_archived: bool = Field(False, description="Include archived attempts")
    scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs to filter by")
    infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")


class ListPracticeResponse(HistoryResponse):
    """Client-facing API response for practice list (paginated history)."""

    pass
