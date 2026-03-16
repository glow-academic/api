"""Types for leaderboard artifact get bundle."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.auth.types import AnalyticsFacets
from app.infra.v5_types import FilterOption


class LeaderboardRequest(BaseModel):
    """Request for getting leaderboard artifact bundle (top sections)."""

    start_date: str | None = Field(None, description="Filter start date")
    end_date: str | None = Field(None, description="Filter end date")
    cohort_ids: list[UUID] | None = Field(None, description="Cohort IDs to filter by")
    department_ids: list[UUID] | None = Field(None, description="Department IDs to filter by")
    simulation_filters: list[str] | None = Field(None, description="Simulation filter strings")
    target_profile_id: UUID | None = Field(None, description="Target profile ID to scope data")

    # Backward-compatible singular filter.
    cohort_id: UUID | None = Field(None, description="Single cohort ID (deprecated)")


class ListLeaderboardRequest(BaseModel):
    """Request for leaderboard list endpoint (bottom table, paginated)."""

    start_date: str | None = Field(None, description="Filter start date")
    end_date: str | None = Field(None, description="Filter end date")
    cohort_ids: list[UUID] | None = Field(None, description="Cohort IDs to filter by")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation IDs to filter by")
    department_ids: list[UUID] | None = Field(None, description="Department IDs to filter by")
    simulation_filters: list[str] | None = Field(None, description="Simulation filter strings")
    target_profile_id: UUID | None = Field(None, description="Target profile ID to scope data")

    # Backward-compatible singular filters.
    cohort_id: UUID | None = Field(None, description="Single cohort ID (deprecated)")
    simulation_id: UUID | None = Field(None, description="Single simulation ID (deprecated)")

    scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs to filter by")
    search: str | None = Field(None, description="Search string for profiles")
    sort_by: str = Field(default="highest_score", description="Sort field name")
    sort_order: str = Field(default="desc", description="Sort direction (asc or desc)")

    page_limit: int = Field(default=50, ge=1, le=200, description="Max items per page")
    page_offset: int = Field(default=0, ge=0, description="Pagination offset")


class LeaderboardMetric(BaseModel):
    """Metric envelope expected by leaderboard UI."""

    has_data: bool | None = Field(None, description="Whether metric has any data")
    method: str | None = Field(None, description="Aggregation method used")
    current_value: float | int | None = Field(None, description="Current metric value")
    key_field: str | None = Field(None, description="Key field name for the metric")
    trend_data: list[str] | None = Field(None, description="Trend data points")
    data_points: list[str] | None = Field(None, description="Raw data point values")
    hover: str | None = Field(None, description="Hover tooltip text")


class LeaderboardMetricsEntry(BaseModel):
    """Row metrics for leaderboard cards and table."""

    total_attempts: LeaderboardMetric | None = Field(None, description="Total attempts metric")
    highest_score_avg: LeaderboardMetric | None = Field(None, description="Highest score average metric")
    messages_per_session: LeaderboardMetric | None = Field(None, description="Messages per session metric")
    persona_response_seconds: LeaderboardMetric | None = Field(None, description="Persona response time metric")
    time_spent_minutes: LeaderboardMetric | None = Field(None, description="Time spent metric in minutes")
    improvement_rate_per_day: LeaderboardMetric | None = Field(None, description="Daily improvement rate metric")
    perfect_score_count: LeaderboardMetric | None = Field(None, description="Perfect score count metric")
    quickest_pass_minutes: LeaderboardMetric | None = Field(None, description="Quickest pass time metric")


class LeaderboardDataRow(BaseModel):
    """Normalized leaderboard row consumed by UI."""

    rank: int | None = Field(None, description="Leaderboard rank position")
    profile_id: str | None = Field(None, description="Profile identifier")
    name: str | None = Field(None, description="Profile display name")
    simulation_ids: list[str] | None = Field(None, description="Associated simulation IDs")
    scenario_ids: list[str] | None = Field(None, description="Associated scenario IDs")
    metrics_entry: LeaderboardMetricsEntry | None = Field(None, description="Row-level metric values")


class LeaderboardSectionStatus(BaseModel):
    """Section-level status metadata."""

    has_data: bool = Field(False, description="Whether section has any data")
    status: str = Field("neutral", description="Section status indicator")
    note: str | None = Field(None, description="Optional status note")


class LeaderboardHeaderMetrics(BaseModel):
    """Top-level leaderboard summary metrics."""

    total_profiles: LeaderboardMetric = Field(default_factory=LeaderboardMetric, description="Total profiles metric")
    total_attempts: LeaderboardMetric = Field(default_factory=LeaderboardMetric, description="Total attempts metric")
    average_score: LeaderboardMetric = Field(default_factory=LeaderboardMetric, description="Average score metric")
    perfect_scores: LeaderboardMetric = Field(default_factory=LeaderboardMetric, description="Perfect scores metric")


class LeaderboardAccoladeWinner(BaseModel):
    """Winner summary for a leaderboard accolade."""

    profile_id: str | None = Field(None, description="Winner profile identifier")
    name: str | None = Field(None, description="Winner display name")
    value: float | int | None = Field(None, description="Winning metric value")
    details: str | None = Field(None, description="Additional accolade details")


class LeaderboardAccoladeWinners(BaseModel):
    """Deterministic accolade winners computed server-side."""

    highest_scorer: LeaderboardAccoladeWinner | None = Field(None, description="Highest scorer accolade winner")
    perfect_score: LeaderboardAccoladeWinner | None = Field(None, description="Perfect score accolade winner")
    longest_convo: LeaderboardAccoladeWinner | None = Field(None, description="Longest conversation accolade winner")
    response_times: LeaderboardAccoladeWinner | None = Field(None, description="Best response times accolade winner")
    quickest_pass: LeaderboardAccoladeWinner | None = Field(None, description="Quickest pass accolade winner")
    the_persistent: LeaderboardAccoladeWinner | None = Field(None, description="Most persistent accolade winner")
    marathon_runner: LeaderboardAccoladeWinner | None = Field(None, description="Marathon runner accolade winner")
    rapid_riser: LeaderboardAccoladeWinner | None = Field(None, description="Rapid riser accolade winner")


class LeaderboardSections(BaseModel):
    """Business-computed section skeletons (built in permissions.py)."""

    header_metrics: LeaderboardHeaderMetrics = Field(
        default_factory=LeaderboardHeaderMetrics, description="Header summary metrics"
    )
    rankings: LeaderboardSectionStatus = Field(default_factory=LeaderboardSectionStatus, description="Rankings section status")
    accolades: LeaderboardSectionStatus = Field(
        default_factory=LeaderboardSectionStatus, description="Accolades section status"
    )
    trends: LeaderboardSectionStatus = Field(default_factory=LeaderboardSectionStatus, description="Trends section status")
    filters: LeaderboardSectionStatus = Field(default_factory=LeaderboardSectionStatus, description="Filters section status")
    accolade_winners: LeaderboardAccoladeWinners = Field(
        default_factory=LeaderboardAccoladeWinners, description="Computed accolade winners"
    )


class LeaderboardViews(BaseModel):
    """Raw MV slices used to compute leaderboard sections (deprecated — always empty)."""

    attempt_facts: list[Any] = Field(default_factory=list, description="Raw attempt fact slices")
    chat_facts: list[Any] = Field(default_factory=list, description="Raw chat fact slices")
    daily_metrics: list[Any] = Field(default_factory=list, description="Raw daily metric slices")
    profile_metrics: list[Any] = Field(default_factory=list, description="Raw profile metric slices")


class LeaderboardProfileResource(BaseModel):
    profile_id: str | None = Field(None, description="Profile identifier")
    name: str | None = Field(None, description="Profile display name")
    role: str | None = Field(None, description="Profile role")


class LeaderboardSimulationResource(BaseModel):
    simulation_id: str | None = Field(None, description="Simulation identifier")
    name: str | None = Field(None, description="Simulation display name")
    description: str | None = Field(None, description="Simulation description")


class LeaderboardScenarioResource(BaseModel):
    scenario_id: str | None = Field(None, description="Scenario identifier")
    name: str | None = Field(None, description="Scenario display name")
    description: str | None = Field(None, description="Scenario description")


class LeaderboardResources(BaseModel):
    """Resource metadata keyed by ID for normalized hydration."""

    profiles: dict[str, LeaderboardProfileResource] = Field(default_factory=dict, description="Profile resources keyed by ID")
    simulations: dict[str, LeaderboardSimulationResource] = Field(default_factory=dict, description="Simulation resources keyed by ID")
    scenarios: dict[str, LeaderboardScenarioResource] = Field(default_factory=dict, description="Scenario resources keyed by ID")


class LeaderboardResponse(BaseModel):
    """Response for leaderboard get (top sections only).

    Includes inline analytics facets for SSR filter rendering.
    """

    sections: LeaderboardSections = Field(default_factory=LeaderboardSections, description="Computed leaderboard sections")
    resources: LeaderboardResources = Field(default_factory=LeaderboardResources, description="Resource metadata for hydration")
    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")


class ListLeaderboardResponse(BaseModel):
    """Response for leaderboard list (profile rows, paginated)."""

    data: list[LeaderboardDataRow] = Field(default_factory=list, description="Leaderboard profile rows")
    resources: LeaderboardResources = Field(default_factory=LeaderboardResources, description="Resource metadata for hydration")
    total_count: int = Field(default=0, description="Total number of matching records")

    simulation_options: list[FilterOption] = Field(default_factory=list, description="Simulation filter options")
    profile_options: list[FilterOption] = Field(default_factory=list, description="Profile filter options")


# =============================================================================
# Export Types
# =============================================================================


class ExportLeaderboardApiResponse(BaseModel):
    """Response model for leaderboard export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")
