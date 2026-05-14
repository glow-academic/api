"""Types for pricing artifact."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import FilterOption
from app.infra.auth.types import AnalyticsFacets


class PricingDailyItem(BaseModel):
    """A single day+model aggregation bucket."""

    date_key: str = Field(..., description="Date bucket key")
    model_id: str | None = Field(None, description="Associated model identifier")
    total_cost: Decimal = Field(Decimal("0"), description="Total cost for this bucket")
    run_count: int = Field(0, description="Number of runs in this bucket")


class PricingRequest(BaseModel):
    """Request for pricing get endpoint (top chart)."""

    # Date filters (accept both naming conventions)
    start_date: datetime | None = Field(default=None, description="Filter start date")
    end_date: datetime | None = Field(default=None, description="Filter end date")
    date_from: datetime | None = Field(default=None, description="Alias for start date")
    date_to: datetime | None = Field(default=None, description="Alias for end date")
    department_ids: list[UUID] = Field(default_factory=list, description="Department IDs to filter by")
    page_limit: int = Field(100, ge=1, le=500, description="Max chart items per page")
    page_offset: int = Field(0, ge=0, description="Chart pagination offset")
    # History fields removed — paginated groups list fetched via /system/groups.
    # See ListPricingRequest below for the filter shape that endpoint accepts.

    @property
    def effective_date_from(self) -> datetime | None:
        """Get effective start date (prefers start_date over date_from)."""
        return self.start_date or self.date_from

    @property
    def effective_date_to(self) -> datetime | None:
        """Get effective end date (prefers end_date over date_to)."""
        return self.end_date or self.date_to


class ListPricingRequest(BaseModel):
    """Request for /system/groups endpoint (paginated groups with cost data).

    Canonical paginated groups list. Promoted from /system/pricing/search.
    Filter fields here mirror the previous PricingRequest.history_* set so
    consumers that used to drive the inline history pass them through.
    """

    # Date filters
    start_date: datetime | None = Field(default=None, description="Filter start date")
    end_date: datetime | None = Field(default=None, description="Filter end date")
    date_from: datetime | None = Field(default=None, description="Alias for start date")
    date_to: datetime | None = Field(default=None, description="Alias for end date")

    # Scope filters (mirrored from the old PricingRequest.history_* fields).
    department_ids: list[UUID] | None = Field(None, description="Department IDs to filter by")
    model_id: UUID | None = Field(None, description="Model UUID to filter by (legacy singular)")
    model_ids: list[UUID] | None = Field(None, description="Model UUIDs to filter by (multi, preferred)")
    profile_ids: list[UUID] | None = Field(None, description="Profile UUIDs (human users) to filter by")
    agent_ids: list[UUID] | None = Field(None, description="Agent UUIDs (LLM agents) to filter by")
    search: str | None = Field(None, description="Group name search (ILIKE)")

    # Pagination + sort
    page: int = Field(0, description="Pagination page number")
    page_size: int = Field(50, description="Items per page")
    sort_by: str = Field("date", description="Sort field (date | total_cost | total_tokens | run_count)")
    sort_order: str = Field("desc", description="Sort direction (asc or desc)")

    @property
    def effective_date_from(self) -> datetime | None:
        return self.start_date or self.date_from

    @property
    def effective_date_to(self) -> datetime | None:
        return self.end_date or self.date_to


class PricingResources(BaseModel):
    """Pricing resource metadata."""

    agents: dict[str, dict] = Field(default_factory=dict, description="Agent resources keyed by ID")
    models: dict[str, dict] = Field(default_factory=dict, description="Model resources keyed by ID")


class PricingHistoryResponse(BaseModel):
    """Embedded pricing group history for the pricing bundle endpoint."""

    items: list["PricingGroupItem"] = Field(default_factory=list, description="Pricing group rows")
    total_count: int = Field(default=0, description="Total number of matching records")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(50, description="Items per page")
    total_pages: int = Field(0, description="Total number of pages")


class PricingResponse(BaseModel):
    """Response for pricing get (top chart)."""

    daily: list[PricingDailyItem] = Field(default_factory=list, description="Daily pricing aggregations")
    resources: PricingResources = Field(default_factory=PricingResources, description="Pricing resource metadata")
    total_count: int = Field(default=0, description="Total number of matching records")

    model_options: list[FilterOption] = Field(default_factory=list, description="Model filter options")
    agent_options: list[FilterOption] = Field(default_factory=list, description="Agent filter options")
    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")
    # Paginated history is no longer inline on /pricing/get — fetch via
    # /system/groups. Field retained as always-None for prop-shape compat
    # with clients that merge /system/groups results into the bundle.
    history: PricingHistoryResponse | None = Field(None, description="Always null on /pricing/get — use /system/groups instead")


class PricingGroupItem(BaseModel):
    """A single group row in the pricing list."""

    group_id: UUID = Field(..., description="Pricing group identifier")
    session_id: UUID | None = Field(None, description="Associated session ID")
    group_name: str | None = Field(None, description="Group display name")
    first_run_at: datetime | None = Field(None, description="Timestamp of first run")
    last_run_at: datetime | None = Field(None, description="Timestamp of last run")
    run_count: int = Field(0, description="Number of runs in the group")
    total_input_tokens: int = Field(0, description="Total input tokens consumed")
    total_output_tokens: int = Field(0, description="Total output tokens generated")
    total_tokens: int = Field(0, description="Total tokens used")
    total_cost: Decimal = Field(Decimal("0"), description="Total cost for the group")
    agent_ids: list[UUID] | None = Field(None, description="Associated agent IDs")
    model_ids: list[UUID] | None = Field(None, description="Associated model IDs")
    profile_ids: list[UUID] | None = Field(None, description="Profile IDs (human users) who triggered runs in this group")
    agent_names: list[str] | None = Field(None, description="Associated agent names")
    model_names: list[str] | None = Field(None, description="Associated model names")
    profile_names: list[str] | None = Field(
        None,
        description="Display names of the profiles (human users) who triggered runs in this group",
    )


class ListPricingResponse(BaseModel):
    """Response for pricing list (group history, paginated)."""

    data: list[PricingGroupItem] = Field(default_factory=list, description="Pricing group rows")
    total_count: int = Field(default=0, description="Total number of matching records")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(50, description="Items per page")
    total_pages: int = Field(0, description="Total number of pages")


# =============================================================================
# Export Types
# =============================================================================


class ExportPricingApiResponse(BaseModel):
    """Response model for pricing export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsPricingApiRequest(BaseModel):
    """Request model for pricing generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsPricingListItem(BaseModel):
    """Single generation group in the pricing generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsPricingApiResponse(BaseModel):
    """Response model for pricing generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsPricingListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemPricingApiRequest(BaseModel):
    """Request model for pricing problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")


class ProblemPricingApiResponse(BaseModel):
    """Response model for pricing problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
