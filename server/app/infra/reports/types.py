"""Types for reports artifact get bundle."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.auth.types import AnalyticsFacets
from app.infra.v5_types import FilterOption


class ReportsRequest(BaseModel):
    """Request for getting reports artifact bundle."""

    start_date: str | None = Field(None, description="Filter start date")
    end_date: str | None = Field(None, description="Filter end date")
    cohort_ids: list[UUID] | None = Field(None, description="Cohort IDs to filter by")
    simulation_ids: list[UUID] | None = Field(None, description="Simulation IDs to filter by")
    department_ids: list[UUID] | None = Field(None, description="Department IDs to filter by")
    roles: list[str] | None = Field(None, description="Roles to filter by")
    simulation_filters: list[str] | None = Field(None, description="Simulation filter strings")
    actor_profile_id: UUID | None = Field(None, description="Acting user profile ID")
    target_profile_id: UUID | None = Field(None, description="Target profile ID to scope data")

    profile_ids: list[UUID] | None = Field(None, description="Profile IDs to filter by")
    scenario_ids: list[UUID] | None = Field(None, description="Scenario IDs to filter by")
    search: str | None = Field(None, description="Search string")
    sort_by: str = Field(default="date", description="Sort field name")
    sort_order: str = Field(default="desc", description="Sort direction (asc or desc)")

    page_limit: int = Field(default=50, ge=1, le=200, description="Max items per page")
    page_offset: int = Field(default=0, ge=0, description="Pagination offset")


class ReportsMetric(BaseModel):
    """Small, reusable metric envelope for section outputs."""

    current_value: float | int | None = Field(None, description="Current metric value")
    has_data: bool = Field(False, description="Whether metric has any data")
    method: str | None = Field(None, description="Aggregation method used")
    data_points: list["ReportsDataPoint"] = Field(default_factory=list, description="Metric data points")
    hover: "ReportsMetricHover | None" = Field(None, description="Hover tooltip payload")
    status: str = Field("neutral", description="Metric status indicator")


class ReportsDataPoint(BaseModel):
    """Metric trend point (lightweight equivalent of SQL data_point type)."""

    profile_id: str | None = Field(None, description="Associated profile ID")
    date: str | None = Field(None, description="Date of the data point")
    value: float | int | None = Field(None, description="Data point value")
    simulation_id: str | None = Field(None, description="Associated simulation ID")
    scenario_id: str | None = Field(None, description="Associated scenario ID")
    attempt_id: str | None = Field(None, description="Associated attempt ID")


class ReportsMetricHover(BaseModel):
    """Metric hover payload (compatible field names with legacy SQL bundle)."""

    mean: int = Field(0, description="Mean value")
    median: int = Field(0, description="Median value")
    mode: int = Field(0, description="Mode value")
    count: int = Field(0, description="Total count")
    completed: int = Field(0, description="Number completed")
    total: int = Field(0, description="Total number")
    percent: int = Field(0, description="Percentage value")
    top: list[int] = Field(default_factory=list, description="Top values list")
    mean_seconds: int = Field(0, description="Mean time in seconds")
    median_seconds: int = Field(0, description="Median time in seconds")
    samples: int = Field(0, description="Number of samples")
    avg_score_percent: int = Field(0, description="Average score percentage")
    avg_minutes: int = Field(0, description="Average duration in minutes")
    efficiency: int = Field(0, description="Efficiency score")
    tracked: int = Field(0, description="Number tracked")
    stagnant: int = Field(0, description="Number stagnant")
    rate_percent: int = Field(0, description="Rate as percentage")
    total_minutes: int = Field(0, description="Total time in minutes")
    total_hours: float = Field(0.0, description="Total time in hours")
    attempts: int = Field(0, description="Number of attempts")
    unique_simulations: int = Field(0, description="Number of unique simulations")
    per_simulation_mean: int = Field(0, description="Mean per simulation")


class ReportsProfileMetrics(BaseModel):
    """Per-profile metric bundle aligned to legacy report metric families."""

    average_score: ReportsMetric = Field(default_factory=ReportsMetric, description="Average score metric")
    completion_percentage: ReportsMetric = Field(default_factory=ReportsMetric, description="Completion percentage metric")
    first_attempt_pass_rate: ReportsMetric = Field(default_factory=ReportsMetric, description="First attempt pass rate metric")
    highest_score: ReportsMetric = Field(default_factory=ReportsMetric, description="Highest score metric")
    messages_per_session: ReportsMetric = Field(default_factory=ReportsMetric, description="Messages per session metric")
    persona_response_times: ReportsMetric = Field(default_factory=ReportsMetric, description="Persona response times metric")
    session_efficiency: ReportsMetric = Field(default_factory=ReportsMetric, description="Session efficiency metric")
    stagnation_rate: ReportsMetric = Field(default_factory=ReportsMetric, description="Stagnation rate metric")
    time_spent: ReportsMetric = Field(default_factory=ReportsMetric, description="Time spent metric")
    total_attempts: ReportsMetric = Field(default_factory=ReportsMetric, description="Total attempts metric")


class ReportsHeaderMetrics(BaseModel):
    """Header summary metrics."""

    total_attempts: ReportsMetric = Field(default_factory=ReportsMetric, description="Total attempts metric")
    average_score: ReportsMetric = Field(default_factory=ReportsMetric, description="Average score metric")
    completion_percentage: ReportsMetric = Field(default_factory=ReportsMetric, description="Completion percentage metric")
    first_attempt_pass_rate: ReportsMetric = Field(default_factory=ReportsMetric, description="First attempt pass rate metric")


class ReportsSectionStatus(BaseModel):
    """Section-level status metadata."""

    has_data: bool = Field(False, description="Whether section has any data")
    status: str = Field("neutral", description="Section status indicator")
    note: str | None = Field(None, description="Optional status note")


class ReportsOverviewRow(BaseModel):
    """Overview row grouped by simulation."""

    simulation_id: str | None = Field(None, description="Simulation identifier")
    attempts: int = Field(0, description="Number of attempts")
    completed_attempts: int = Field(0, description="Number of completed attempts")
    passed_attempts: int = Field(0, description="Number of passing attempts")
    average_score: float | None = Field(None, description="Average score")
    completion_percentage: float | None = Field(None, description="Completion percentage")
    pass_rate: float | None = Field(None, description="Pass rate percentage")


class ReportsOverviewSection(BaseModel):
    """Overview section output."""

    status: ReportsSectionStatus = Field(default_factory=ReportsSectionStatus, description="Section status metadata")
    rows: list[ReportsOverviewRow] = Field(default_factory=list, description="Overview rows by simulation")


class ReportsLeaderboardRow(BaseModel):
    """Leaderboard row from profile metrics."""

    rank: int = Field(..., description="Leaderboard rank position")
    profile_id: str | None = Field(None, description="Profile identifier")
    total_attempts: int = Field(0, description="Total number of attempts")
    average_score: float | None = Field(None, description="Average score")
    highest_score: float | None = Field(None, description="Highest score achieved")
    completion_percentage: float | None = Field(None, description="Completion percentage")
    first_attempt_pass_rate: float | None = Field(None, description="First attempt pass rate")
    profile_metrics: ReportsProfileMetrics | None = Field(None, description="Detailed profile metrics")
    simulation_ids: list[str] = Field(default_factory=list, description="Associated simulation IDs")
    scenario_ids: list[str] = Field(default_factory=list, description="Associated scenario IDs")


class ReportsLeaderboardSection(BaseModel):
    """Leaderboard section output."""

    status: ReportsSectionStatus = Field(default_factory=ReportsSectionStatus, description="Section status metadata")
    rows: list[ReportsLeaderboardRow] = Field(default_factory=list, description="Leaderboard rows")


class ReportsTrendPoint(BaseModel):
    """Time-series aggregate point."""

    date: str | None = Field(None, description="Date of the trend point")
    attempts: int = Field(0, description="Number of attempts")
    completed_attempts: int = Field(0, description="Number of completed attempts")
    passed_attempts: int = Field(0, description="Number of passing attempts")
    average_score: float | None = Field(None, description="Average score")
    completion_percentage: float | None = Field(None, description="Completion percentage")
    pass_rate: float | None = Field(None, description="Pass rate percentage")


class ReportsTrendsSection(BaseModel):
    """Trends section output."""

    status: ReportsSectionStatus = Field(default_factory=ReportsSectionStatus, description="Section status metadata")
    chart_data: list[ReportsTrendPoint] = Field(default_factory=list, description="Trend chart time-series data")


class ReportsHistoryRow(BaseModel):
    """History row from attempt facts."""

    attempt_id: str | None = Field(None, description="Attempt identifier")
    profile_id: str | None = Field(None, description="Associated profile ID")
    simulation_id: str | None = Field(None, description="Associated simulation ID")
    cohort_id: str | None = Field(None, description="Associated cohort ID")
    attempt_created_at: datetime | None = Field(None, description="Attempt creation timestamp")
    attempt_type: str | None = Field(None, description="Type of attempt")
    is_archived: bool = Field(False, description="Whether attempt is archived")
    infinite_mode: bool = Field(False, description="Whether attempt was infinite mode")
    score_percent: float | None = Field(None, description="Score as percentage")
    has_passed: bool = Field(False, description="Whether attempt passed")
    num_chats: int = Field(0, description="Number of chats in attempt")
    num_chats_completed: int = Field(0, description="Number of completed chats")
    total_time_seconds: int = Field(0, description="Total time in seconds")
    scenario_ids: list[str] = Field(default_factory=list, description="Associated scenario IDs")


class ReportsHistorySection(BaseModel):
    """History section output."""

    status: ReportsSectionStatus = Field(default_factory=ReportsSectionStatus, description="Section status metadata")
    rows: list[ReportsHistoryRow] = Field(default_factory=list, description="History rows")


class ReportsSections(BaseModel):
    """Business-computed section skeletons (built in permissions.py)."""

    header_metrics: ReportsHeaderMetrics = Field(default_factory=ReportsHeaderMetrics, description="Header summary metrics")
    overview: ReportsOverviewSection = Field(default_factory=ReportsOverviewSection, description="Overview section data")
    leaderboard: ReportsLeaderboardSection = Field(
        default_factory=ReportsLeaderboardSection, description="Leaderboard section data"
    )
    trends: ReportsTrendsSection = Field(default_factory=ReportsTrendsSection, description="Trends section data")
    history: ReportsHistorySection = Field(default_factory=ReportsHistorySection, description="History section data")


class ReportsViews(BaseModel):
    """Raw MV slices used to compute section outputs (deprecated — always empty)."""

    attempt_facts: list[Any] = Field(default_factory=list, description="Raw attempt fact slices")
    chat_facts: list[Any] = Field(default_factory=list, description="Raw chat fact slices")
    daily_metrics: list[Any] = Field(default_factory=list, description="Raw daily metric slices")
    profile_metrics: list[Any] = Field(default_factory=list, description="Raw profile metric slices")


class ReportsSimulationResource(BaseModel):
    simulation_id: str | None = Field(None, description="Simulation identifier")
    name: str | None = Field(None, description="Simulation display name")
    description: str | None = Field(None, description="Simulation description")


class ReportsProfileResource(BaseModel):
    profile_id: str | None = Field(None, description="Profile identifier")
    name: str | None = Field(None, description="Profile display name")
    role: str | None = Field(None, description="Profile role")
    emails: list[str] = Field(default_factory=list, description="Profile email addresses")
    primary_email: str | None = Field(None, description="Primary email address")


class ReportsScenarioResource(BaseModel):
    scenario_id: str | None = Field(None, description="Scenario identifier")
    name: str | None = Field(None, description="Scenario display name")
    description: str | None = Field(None, description="Scenario description")


class ReportsCohortResource(BaseModel):
    cohort_id: str | None = Field(None, description="Cohort identifier")
    name: str | None = Field(None, description="Cohort display name")


class ReportsPersonaResource(BaseModel):
    persona_id: str | None = Field(None, description="Persona identifier")
    name: str | None = Field(None, description="Persona display name")
    color: str | None = Field(None, description="Persona chart color")
    icon: str | None = Field(None, description="Persona icon identifier")


class ReportsRubricResource(BaseModel):
    rubric_id: str | None = Field(None, description="Rubric identifier")
    name: str | None = Field(None, description="Rubric display name")
    description: str | None = Field(None, description="Rubric description")


class ReportsResources(BaseModel):
    """Resource metadata keyed by ID for normalized hydration."""

    simulations: dict[str, ReportsSimulationResource] = Field(default_factory=dict, description="Simulation resources keyed by ID")
    profiles: dict[str, ReportsProfileResource] = Field(default_factory=dict, description="Profile resources keyed by ID")
    scenarios: dict[str, ReportsScenarioResource] = Field(default_factory=dict, description="Scenario resources keyed by ID")
    cohorts: dict[str, ReportsCohortResource] = Field(default_factory=dict, description="Cohort resources keyed by ID")
    personas: dict[str, ReportsPersonaResource] = Field(default_factory=dict, description="Persona resources keyed by ID")
    rubrics: dict[str, ReportsRubricResource] = Field(default_factory=dict, description="Rubric resources keyed by ID")


class ReportsResponse(BaseModel):
    """Target reports artifact bundle shape."""

    sections: ReportsSections = Field(default_factory=ReportsSections, description="Computed report sections")
    views: ReportsViews = Field(default_factory=ReportsViews, description="Raw MV view slices (deprecated)")
    resources: ReportsResources = Field(default_factory=ReportsResources, description="Resource metadata for hydration")
    total_count: int = Field(default=0, description="Total number of matching records")

    simulation_options: list[FilterOption] = Field(default_factory=list, description="Simulation filter options")
    profile_options: list[FilterOption] = Field(default_factory=list, description="Profile filter options")
    scenario_options: list[FilterOption] = Field(default_factory=list, description="Scenario filter options")

    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")


class ExportReportsApiResponse(BaseModel):
    """Response model for reports export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")
