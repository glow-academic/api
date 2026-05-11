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
    department_ids: list[UUID] = Field(default_factory=list, description="Department IDs to filter by")
    role_ids: list[UUID] = Field(default_factory=list, description="Role resource IDs to filter profiles by")
    page_limit: int = Field(50, ge=1, le=200, description="Max summary items per page")
    page_offset: int = Field(0, ge=0, description="Summary pagination offset")
    summary_profile_id: UUID | None = Field(None, description="Profile ID to focus the summary card")
    # History fields removed — paginated sessions list fetched via /system/sessions.
    # See ListActivityRequest below for the filter shape that endpoint accepts.


class ListActivityRequest(BaseModel):
    """Request for activity list endpoint (session history, paginated)."""

    date_from: datetime | None = Field(default=None, description="Filter start date")
    date_to: datetime | None = Field(default=None, description="Filter end date")
    department_ids: list[UUID] = Field(default_factory=list, description="Department IDs to filter by")
    role_ids: list[UUID] = Field(default_factory=list, description="Role resource IDs to filter profiles by")

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


class ActivityProblemItem(BaseModel):
    """Recent problem displayed on the activity page."""

    problem_id: UUID = Field(..., description="Problem identifier")
    profile_id: UUID | None = Field(None, description="Profile that reported the problem")
    profile_name: str | None = Field(None, description="Profile display name")
    session_id: UUID | None = Field(None, description="Associated session")
    type: str = Field(..., description="Problem type")
    message: str = Field(..., description="Problem message")
    resolved: bool = Field(False, description="Whether the problem is resolved")
    created_at: datetime = Field(..., description="Problem creation timestamp")


class ActivityResources(BaseModel):
    """Activity resource metadata."""

    profiles: dict[str, dict] = Field(default_factory=dict, description="Profile resources keyed by ID")


class ActivityHistoryResponse(BaseModel):
    """Embedded activity session history for the activity bundle endpoint."""

    items: list[SessionListItem] = Field(default_factory=list, description="Session history items")
    total_count: int = Field(default=0, description="Total number of matching records")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(50, description="Items per page")
    total_pages: int = Field(0, description="Total number of pages")


class ActivityResponse(BaseModel):
    """Response with activity data (top cards)."""

    # Header metrics (flat)
    sessions_count: int = Field(0, description="Total number of sessions")
    active_profiles_count: int = Field(0, description="Number of active profiles")
    logins_count: int = Field(0, description="Total number of logins")
    emulations_count: int = Field(0, description="Total number of emulations")
    # Profile summary
    profile_summary: list[ProfileSummaryItem] = Field(default_factory=list, description="Per-profile activity summaries")
    # Recent problems
    problems: list[ActivityProblemItem] = Field(default_factory=list, description="Recent problems for the activity panel")
    # Resources
    resources: ActivityResources = Field(default_factory=ActivityResources, description="Activity resource metadata")
    # Inline analytics facets
    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")
    # Paginated history is no longer inline on /activity/get — fetch via
    # /system/sessions. Field retained as always-None for prop-shape compat
    # with clients that merge /system/sessions results into the bundle.
    history: ActivityHistoryResponse | None = Field(None, description="Always null on /activity/get — use /system/sessions instead")


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


# =============================================================================
# Problem Types
# =============================================================================


class CreateProblemApiRequest(BaseModel):
    """Request for creating a problem entry."""

    type: str = Field(..., description="Problem type: feature, bug, question, or other")
    message: str = Field(..., description="Problem description message")


class CreateProblemApiResponse(BaseModel):
    """Response for creating a problem entry."""

    problem_id: UUID = Field(..., description="ID of the created problem")
    success: bool = Field(..., description="Whether the problem was created successfully")
    message: str = Field(..., description="Status message")


# =============================================================================
# Resolve Types
# =============================================================================


class ResolveProblemApiRequest(BaseModel):
    """Request for resolving a problem entry."""

    problem_id: UUID = Field(..., description="ID of the problem to resolve")
    resolved: bool = Field(True, description="Whether the problem is resolved")


class ResolveProblemApiResponse(BaseModel):
    """Response for resolving a problem entry."""

    problem_id: UUID = Field(..., description="ID of the resolved problem")
    resolved: bool = Field(..., description="Current resolved status")
    updated_at: datetime = Field(..., description="Timestamp of the update")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsActivityApiRequest(BaseModel):
    """Request model for activity generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Filter by creation date (>=)")
    date_to: datetime | None = Field(None, description="Filter by creation date (<=)")
    page_limit: int = Field(50, ge=1, description="Max items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsActivityListItem(BaseModel):
    """Single generation group in the activity generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="Session that created this group")
    group_name: str | None = Field(None, description="Optional human-readable group name")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsActivityApiResponse(BaseModel):
    """Response model for activity generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsActivityListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")
