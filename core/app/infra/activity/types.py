"""Types for activity artifact."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.auth.types import AnalyticsFacets
from app.infra.session.types import SessionListItem


class ActivityRequest(BaseModel):
    """Request for getting activity data (top cards)."""

    date_from: datetime | None = Field(default=None, description="Filter start date")
    date_to: datetime | None = Field(default=None, description="Filter end date")
    department_ids: list[str] = Field(default_factory=list, description="Department IDs to filter by")
    roles: list[str] = Field(default_factory=list, description="Roles to filter by")


class ListActivityRequest(BaseModel):
    """Request for activity list endpoint (session history, paginated)."""

    date_from: datetime | None = Field(default=None, description="Filter start date")
    date_to: datetime | None = Field(default=None, description="Filter end date")
    department_ids: list[str] = Field(default_factory=list, description="Department IDs to filter by")
    roles: list[str] = Field(default_factory=list, description="Roles to filter by")

    active: bool | None = Field(default=None, description="Filter by active status")
    page: int = Field(0, description="Pagination page number")
    page_size: int = Field(50, description="Items per page")
    sort_order: str = Field("desc", description="Sort direction (asc or desc)")


class ProfileSummaryItem(BaseModel):
    """Per-profile aggregate stats for the summary card."""

    profile_id: UUID | None = Field(None, description="Profile identifier")
    profile_name: str | None = Field(None, description="Profile display name")
    sessions_count: int = Field(0, description="Number of sessions")
    logins_count: int = Field(0, description="Number of logins")
    grants_count: int = Field(0, description="Number of grants")
    problems_count: int = Field(0, description="Number of problems")
    activity_count: int = Field(0, description="Total activity count")


class ActivityResources(BaseModel):
    """Activity resource metadata."""

    profiles: dict[str, dict] = Field(default_factory=dict, description="Profile resources keyed by ID")


class ActivityResponse(BaseModel):
    """Response with activity data (top cards)."""

    # Header metrics (flat)
    sessions_count: int = Field(0, description="Total number of sessions")
    active_profiles_count: int = Field(0, description="Number of active profiles")
    logins_count: int = Field(0, description="Total number of logins")
    emulations_count: int = Field(0, description="Total number of emulations")
    # Profile summary
    profile_summary: list[ProfileSummaryItem] = Field(default_factory=list, description="Per-profile activity summaries")
    # Resources
    resources: ActivityResources = Field(default_factory=ActivityResources, description="Activity resource metadata")
    # Inline analytics facets
    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")


class ListActivityResponse(BaseModel):
    """Response for activity list (session history, paginated)."""

    data: list[SessionListItem] = Field(default_factory=list, description="Session history items")
    total_count: int = Field(default=0, description="Total number of matching records")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(50, description="Items per page")
    total_pages: int = Field(0, description="Total number of pages")


# =============================================================================
# Export Types
# =============================================================================


class ExportActivityApiResponse(BaseModel):
    """Response model for activity export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")
