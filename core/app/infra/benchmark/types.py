"""Types for benchmark artifact."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.auth.types import AnalyticsFacets
from app.infra.api_types import FilterOption


class BenchmarkRequest(BaseModel):
    """Request for getting benchmark data."""

    start_date: str | None = Field(None, description="Filter start date")
    end_date: str | None = Field(None, description="Filter end date")
    department_ids: list[str] = Field(default_factory=list, description="Department IDs to filter by")
    # History params
    history_page: int = Field(0, description="History pagination page number")
    history_page_size: int = Field(10, description="History items per page")
    history_eval_ids: list[str] = Field(default_factory=list, description="Eval IDs for history filter")
    history_search: str | None = Field(None, description="Search string for history")
    history_archived: bool | None = Field(None, description="Filter by archived status")
    history_sort_by: str = Field("date", description="History sort field")
    history_sort_order: str = Field("desc", description="History sort direction")


class BenchmarkEvalOperational(BaseModel):
    """Eval card for the benchmark page — analogous to ChatSimulationOperational."""

    # Identity
    eval_id: str = Field(..., description="Eval identifier")
    eval_name: str | None = Field(None, description="Eval display name")
    eval_description: str | None = Field(None, description="Eval description")

    # Models (analogous to scenarios in home)
    model_ids: list[str] = Field(default_factory=list, description="Associated model IDs")

    # Stats
    total_tests: int = Field(0, description="Total number of tests")
    archived_tests: int = Field(0, description="Number of archived tests")
    total_invocations: int = Field(0, description="Total number of invocations")
    completed_invocations: int = Field(0, description="Number of completed invocations")
    highest_score: float | None = Field(None, description="Highest score achieved")
    has_passed: bool = Field(False, description="Whether eval has been passed")

    # Computed
    status: str = Field("not-started", description="Eval status")
    infinite_mode: bool = Field(False, description="Whether eval uses infinite mode")

    # Departments
    department_ids: list[str] = Field(default_factory=list, description="Associated department IDs")

    # Rubric
    rubric_ids: list[str] = Field(default_factory=list, description="Associated rubric IDs")


class BenchmarkDepartmentItem(BaseModel):
    """Department resource for benchmark."""

    department_id: str = Field(..., description="Department identifier")
    name: str | None = Field(None, description="Department display name")
    description: str | None = Field(None, description="Department description")


class BenchmarkHistoryItem(BaseModel):
    """Single test row in benchmark history list — mirrors HistoryItem shape."""

    test_id: str = Field(..., description="Test identifier")
    date: str | None = Field(None, description="Formatted date string of the test")
    profile_id: UUID | None = Field(None, description="UUID of the profile who owns the test")
    profile_name: str | None = Field(None, description="Display name of the profile")

    eval_id: str | None = Field(None, description="Parent eval ID")
    eval_name: str | None = Field(None, description="Parent eval name")

    # Each test has exactly one rubric
    rubric_id: str | None = Field(None, description="Rubric ID for this test")
    rubric_name: str | None = Field(None, description="Rubric display name")

    # Models analog of scenarios
    num_models: int | None = Field(None, description="Total number of models in the test")
    num_models_completed: int | None = Field(None, description="Number of models completed")
    model_ids: list[str] | None = Field(None, description="UUIDs of associated models")
    model_names: list[str] | None = Field(None, description="Display names of associated models")

    # Score (canonical 0-100 int)
    score: int | None = Field(None, description="Overall test score (0-100)")
    score_status: str | None = Field(None, description="Score status label (e.g. high, medium, low)")
    pass_pct: int | None = Field(None, description="Pass percentage threshold from rubric")

    # Actions
    show_view: bool | None = Field(None, description="Whether the view action is available")
    show_continue: bool | None = Field(None, description="Whether the continue action is available")
    is_archived: bool | None = Field(None, description="Whether the test is archived")

    # Modes (no time_limit on evals)
    infinite_mode: bool | None = Field(None, description="Whether the test uses infinite mode")

    # Metadata
    department_ids: list[str] | None = Field(None, description="Associated department IDs")


class BenchmarkHistoryResponse(BaseModel):
    """Paginated history response."""

    data: list[BenchmarkHistoryItem] = Field(default_factory=list, description="History items")
    total_count: int = Field(0, description="Total number of matching records")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(10, description="Items per page")
    eval_options: list[FilterOption] = Field(default_factory=list, description="Eval filter options")
    model_options: list[FilterOption] = Field(default_factory=list, description="Model filter options")
    profile_options: list[FilterOption] = Field(default_factory=list, description="Profile filter options")
    rubric_options: list[FilterOption] = Field(default_factory=list, description="Rubric filter options")


class BenchmarkResponse(BaseModel):
    """Response with benchmark data."""

    evals: list[BenchmarkEvalOperational] = Field(default_factory=list, description="Eval cards for benchmark page")
    departments: list[BenchmarkDepartmentItem] = Field(default_factory=list, description="Department resources")
    department_options: list[FilterOption] = Field(default_factory=list, description="Department filter options")
    date_range_earliest: str | None = Field(None, description="Earliest date in data range")
    date_range_latest: str | None = Field(None, description="Latest date in data range")
    history: BenchmarkHistoryResponse | None = Field(None, description="Paginated test history")
    analytics: AnalyticsFacets | None = Field(None, description="Inline analytics facets for SSR")


# =============================================================================
# Export Types
# =============================================================================


class ExportBenchmarkApiResponse(BaseModel):
    """Response model for benchmark export."""

    content: str = Field(..., description="Base64-encoded file content")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export file")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsBenchmarkApiRequest(BaseModel):
    """Request model for benchmark generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsBenchmarkListItem(BaseModel):
    """Single generation group in the benchmark generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsBenchmarkApiResponse(BaseModel):
    """Response model for benchmark generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsBenchmarkListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemBenchmarkApiRequest(BaseModel):
    """Request model for benchmark problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")


class ProblemBenchmarkApiResponse(BaseModel):
    """Response model for benchmark problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
