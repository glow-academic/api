"""Types for pricing artifact."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.auth.types import AnalyticsFacets
from app.infra.v5_types import FilterOption


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

    @property
    def effective_date_from(self) -> datetime | None:
        """Get effective start date (prefers start_date over date_from)."""
        return self.start_date or self.date_from

    @property
    def effective_date_to(self) -> datetime | None:
        """Get effective end date (prefers end_date over date_to)."""
        return self.end_date or self.date_to


class ListPricingRequest(BaseModel):
    """Request for pricing list endpoint (group history, paginated)."""

    # Date filters
    start_date: datetime | None = Field(default=None, description="Filter start date")
    end_date: datetime | None = Field(default=None, description="Filter end date")
    date_from: datetime | None = Field(default=None, description="Alias for start date")
    date_to: datetime | None = Field(default=None, description="Alias for end date")

    # Pagination
    page: int = Field(0, description="Pagination page number")
    page_size: int = Field(50, description="Items per page")
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


class PricingResponse(BaseModel):
    """Response for pricing get (top chart)."""

    daily: list[PricingDailyItem] = Field(default_factory=list, description="Daily pricing aggregations")
    resources: PricingResources = Field(default_factory=PricingResources, description="Pricing resource metadata")
    total_count: int = Field(default=0, description="Total number of matching records")

    model_options: list[FilterOption] = Field(default_factory=list, description="Model filter options")
    agent_options: list[FilterOption] = Field(default_factory=list, description="Agent filter options")
    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")


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
    agent_names: list[str] | None = Field(None, description="Associated agent names")
    model_names: list[str] | None = Field(None, description="Associated model names")


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
