"""Types for benchmark test artifacts endpoints.

Three-layer BFF pattern types:
- GetTestArtifactResponse: HTTP client response
- TestInternalData: Core data container (internal layer)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.v5_types import ListFilterSection
from app.tools.entries.messages.types import SearchMessageResponse
from app.tools.entries.test.types import GetTestResponse
from app.tools.entries.test_feedback.types import GetTestFeedbackResponse
from app.tools.entries.test_grade.types import GetTestGradeResponse
from app.tools.entries.test_invocation.types import GetTestInvocationResponse
from app.tools.entries.test_invocation_groups.types import (
    GetTestInvocationGroupsResponse,
)
from app.tools.entries.test_invocation_runs.types import (
    GetTestInvocationRunsResponse,
)

# =============================================================================
# Client-facing types
# =============================================================================


class GetTestArtifactRequest(BaseModel):
    """Request for benchmark test artifact detail."""

    test_id: UUID = Field(..., description="UUID of the test to fetch")


class TestRunItem(BaseModel):
    """A single run row for the UI table, derived from a benchmark invocation."""

    chat_id: str = Field(..., description="ID of the chat")
    invocation_id: str = Field(..., description="ID of the invocation")
    run_id: str | None = Field(None, description="ID of the run")
    group_id: str | None = Field(None, description="ID of the group")
    suite_entry_id: str | None = Field(None, description="ID of the suite entry")
    model_name: str | None = Field(None, description="Name of the model used")
    agent_name: str | None = Field(None, description="Name of the agent used")
    status: str = Field("not_started", description="Run status")
    grade_score: float | None = Field(None, description="Grade score for the run")
    grade_passed: bool | None = Field(None, description="Whether the run passed grading")


class TestStatusSummary(BaseModel):
    total: int = Field(0, description="Total number of invocations")
    completed: int = Field(0, description="Number of completed invocations")
    in_progress: int = Field(0, description="Number of in-progress invocations")
    not_started: int = Field(0, description="Number of not-started invocations")


class TestEntries(BaseModel):
    """Entry payloads grouped by type."""

    tests: list[GetTestResponse] | None = Field(None, description="Test entry payloads")
    invocations: list[GetTestInvocationResponse] | None = Field(None, description="Invocation entry payloads")
    runs: list[GetTestInvocationRunsResponse] | None = Field(None, description="Run entry payloads")
    groups: list[GetTestInvocationGroupsResponse] | None = Field(None, description="Group entry payloads")
    grades: list[GetTestGradeResponse] | None = Field(None, description="Grade entry payloads")
    feedback: list[GetTestFeedbackResponse] | None = Field(None, description="Feedback entry payloads")
    messages: list[SearchMessageResponse] | None = Field(None, description="Message entry payloads")


class TestResources(BaseModel):
    """Resource maps keyed by ID string."""

    evals: dict[str, dict] | None = Field(None, description="Eval resources keyed by ID")
    rubrics: dict[str, dict] | None = Field(None, description="Rubric resources keyed by ID")
    agents: dict[str, dict] | None = Field(None, description="Agent resources keyed by ID")
    models: dict[str, dict] | None = Field(None, description="Model resources keyed by ID")
    voices: dict[str, dict] | None = Field(None, description="Voice resources keyed by ID")
    temperature_levels: dict[str, dict] | None = Field(None, description="Temperature level resources keyed by ID")
    reasoning_levels: dict[str, dict] | None = Field(None, description="Reasoning level resources keyed by ID")
    modalities: dict[str, dict] | None = Field(None, description="Modality resources keyed by ID")
    prompts: dict[str, dict] | None = Field(None, description="Prompt resources keyed by ID")
    instructions: dict[str, dict] | None = Field(None, description="Instruction resources keyed by ID")
    tools: dict[str, dict] | None = Field(None, description="Tool resources keyed by ID")
    qualities: dict[str, dict] | None = Field(None, description="Quality resources keyed by ID")


class GetTestArtifactResponse(BaseModel):
    """Response for benchmark test artifact detail."""

    test: GetTestResponse | None = Field(None, description="Test entry data")
    invocations: list[GetTestInvocationResponse] = Field(default_factory=list, description="Test invocations")
    status: str = Field("pending", description="Overall test status")

    # Hydrated eval info
    eval_name: str | None = Field(None, description="Name of the eval")
    eval_description: str | None = Field(None, description="Description of the eval")
    rubric_name: str | None = Field(None, description="Name of the rubric")
    infinite_mode: bool = Field(False, description="Whether infinite mode is enabled")

    # Runs derived from invocations
    runs: list[TestRunItem] = Field(default_factory=list, description="Run items derived from invocations")

    # Status summary
    status_summary: TestStatusSummary | None = Field(None, description="Summary of invocation statuses")

    # Inline controls data (replaces auth/group resolution for toolbar)
    show_controls: bool = Field(False, description="Whether to show UI controls")
    current_invocation_id: str | None = Field(None, description="ID of the current invocation")
    has_runs_or_groups: bool = Field(False, description="Whether the test has runs or groups")

    # Normalized entries and resources
    entries: TestEntries | None = Field(None, description="Entry payloads by type")
    resources: TestResources | None = Field(None, description="Resource maps keyed by ID")


# =============================================================================
# Internal data (three-layer BFF pattern)
# =============================================================================


@dataclass
class TestInternalData:
    """Core data container returned by get_test_impl().

    Contains all fetched and computed values. Consumer layers
    (get_test_impl_cached, get_test_websocket) reshape this
    into their specific response types.
    """

    # Raw entry results
    test: GetTestResponse | None = None
    invocations: list[GetTestInvocationResponse] = field(default_factory=list)

    # Hydrated eval info
    eval_name: str | None = None
    eval_description: str | None = None

    # Rubric info
    rubric_name_map: dict[UUID, str] = field(default_factory=dict)

    # Computed
    runs: list[TestRunItem] = field(default_factory=list)
    status: str = "pending"
    status_summary: TestStatusSummary = field(default_factory=TestStatusSummary)

    # Inline controls data (replaces auth/group resolution)
    show_controls: bool = False
    current_invocation_id: str | None = None
    has_runs_or_groups: bool = False

    # Full entries + resources
    entries_payload: TestEntries = field(default_factory=TestEntries)
    resources_payload: TestResources = field(default_factory=TestResources)


# =============================================================================
# List types (used by other endpoints)
# =============================================================================


class GetTestListRequest(BaseModel):
    """Request for benchmark test list artifact."""

    start_date: str | None = Field(default=None, description="Start date filter (ISO format)")
    end_date: str | None = Field(default=None, description="End date filter (ISO format)")
    eval_ids: list[str] = Field(default_factory=list, description="Eval IDs to filter by")
    department_ids: list[str] = Field(default_factory=list, description="Department IDs to filter by")
    page: int = Field(default=0, ge=0, description="Page number (0-indexed)")
    page_size: int = Field(default=10, ge=1, le=200, description="Number of items per page")
    search: str | None = Field(default=None, description="Search string")
    status: str | None = Field(default=None, description="Filter by test status")
    archived: bool | None = Field(default=None, description="Filter by archived status")
    sort_by: str = Field(default="date", description="Sort field name")
    sort_order: str = Field(default="desc", description="Sort order: 'asc' or 'desc'")


class TestListFilterOption(BaseModel):
    """Filter option row for tests list."""

    value: str = Field(..., description="Filter option value")
    label: str | None = Field(None, description="Display label for the option")
    count: int = Field(0, description="Number of items matching this option")


class TestListItem(BaseModel):
    """List row for benchmark tests."""

    attempt_id: str = Field(..., description="ID of the test attempt")
    eval_id: str | None = Field(None, description="ID of the eval")
    eval_name: str | None = Field(None, description="Name of the eval")
    eval_description: str | None = Field(None, description="Description of the eval")
    rubric_id: str | None = Field(None, description="ID of the rubric")
    rubric_name: str | None = Field(None, description="Name of the rubric")
    created_at: str | None = Field(None, description="ISO timestamp when test was created")
    archived: bool = Field(False, description="Whether the test is archived")
    status: str = Field("pending", description="Current test status")
    total_runs: int = Field(0, description="Total number of runs")
    completed_runs: int = Field(0, description="Number of completed runs")
    pending_runs: int = Field(0, description="Number of pending runs")


class GetTestListResponse(BaseModel):
    """Response for benchmark tests list artifact."""

    data: list[TestListItem] = Field(default_factory=list, description="Test list items")
    total_count: int = Field(0, description="Total number of matching tests")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(10, description="Number of items per page")
    eval_options: list[TestListFilterOption] = Field(default_factory=list, description="Eval filter options")


class ArchiveTestsRequest(BaseModel):
    """Request for archiving/unarchiving benchmark tests."""

    test_ids: list[UUID] = Field(min_length=1, description="UUIDs of tests to archive/unarchive")
    archived: bool = Field(True, description="Whether to archive or unarchive")


class ArchiveTestsResponse(BaseModel):
    """Response for archiving/unarchiving benchmark tests."""

    updated_count: int = Field(0, description="Number of tests updated")


# =============================================================================
# Search endpoint types
# =============================================================================


class SearchTestItem(BaseModel):
    """Single test row in search results."""

    test_id: UUID = Field(..., description="UUID of the test")
    eval_id: UUID | None = Field(None, description="UUID of the eval")
    eval_name: str | None = Field(None, description="Name of the eval")
    eval_description: str | None = Field(None, description="Description of the eval")
    department_ids: list[UUID] | None = Field(None, description="UUIDs of associated departments")
    test_name: str | None = Field(None, description="Name of the test")
    test_description: str | None = Field(None, description="Description of the test")
    num_invocations: int | None = Field(None, description="Number of invocations")
    infinite_mode: bool | None = Field(None, description="Whether infinite mode is enabled")
    is_dynamic: bool | None = Field(None, description="Whether the test is dynamic")
    archived: bool | None = Field(None, description="Whether the test is archived")
    created_at: str | None = Field(None, description="ISO timestamp when test was created")


class SearchTestApiResponse(BaseModel):
    """Response for test search endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    tests: list[SearchTestItem] | None = Field(None, description="Search result test items")
    eval_filter: ListFilterSection | None = Field(None, description="Eval filter section")
    department_filter: ListFilterSection | None = Field(None, description="Department filter section")
    total_count: int | None = Field(None, description="Total number of matching results")


# =============================================================================
# Export Types
# =============================================================================


class ExportTestApiResponse(BaseModel):
    """Response model for test export."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Name of the exported file")
    mime_type: str = Field(..., description="MIME type of the exported file")
    row_count: int = Field(..., description="Number of rows in the export")
