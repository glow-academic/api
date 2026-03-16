"""Types for benchmark artifact."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.infra.auth.types import AnalyticsFacets
from app.infra.v5_types import FilterOption


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
    """History row for a test — analogous to TestHistoryItem."""

    test_id: str = Field(..., description="Test identifier")
    eval_id: str | None = Field(None, description="Parent eval ID")
    eval_name: str | None = Field(None, description="Parent eval name")
    eval_description: str | None = Field(None, description="Parent eval description")
    created_at: str | None = Field(None, description="Test creation timestamp")
    archived: bool = Field(False, description="Whether test is archived")
    infinite_mode: bool = Field(False, description="Whether test uses infinite mode")

    # Invocation stats
    total_invocations: int = Field(0, description="Total number of invocations")
    completed_invocations: int = Field(0, description="Number of completed invocations")
    pending_invocations: int = Field(0, description="Number of pending invocations")

    # Best score across invocations
    best_score: float | None = Field(None, description="Best score across invocations")
    has_passed: bool = Field(False, description="Whether test has been passed")

    status: str = Field("pending", description="Test status")


class BenchmarkHistoryResponse(BaseModel):
    """Paginated history response."""

    data: list[BenchmarkHistoryItem] = Field(default_factory=list, description="History items")
    total_count: int = Field(0, description="Total number of matching records")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(10, description="Items per page")
    eval_options: list[FilterOption] = Field(default_factory=list, description="Eval filter options")


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
