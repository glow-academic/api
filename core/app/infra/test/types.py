"""Types for benchmark test artifacts endpoints.

Three-layer BFF pattern types:
- GetTestArtifactResponse: HTTP client response
- TestInternalData: Core data container (internal layer)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
# Reuse the canonical rubric/grade shapes from attempt — same data, same
# client consumer (TableRubric). Keeps benchmark and attempt's graded
# view aligned without forking a second set of Pydantic models.
from app.infra.attempt.types import (
    AnalysisEntry,
    FeedbackEntry,
    GradeData,
    GradingStateData,
    RubricStructureData,
)
from app.tools.entries.messages.types import SearchMessageResponse
from app.tools.entries.test.types import GetTestResponse
from app.tools.entries.test_feedback.types import GetTestFeedbackResponse
from app.tools.entries.test_grade.types import GetTestGradeResponse
from app.tools.entries.test_invocation.types import GetTestInvocationResponse
from app.tools.entries.test_invocation_runs.types import (
    GetTestInvocationRunsResponse,
)
from app.tools.entries.test_invocation_traces.types import (
    GetTestInvocationTracesResponse,
)

# =============================================================================
# Client-facing types
# =============================================================================


class GetTestArtifactRequest(BaseModel):
    """Request for benchmark test artifact detail."""

    test_id: UUID = Field(..., description="UUID of the test to fetch")

    # Picker pagination — drives the bottom composer's run-config list.
    # Two-axis (groups-first):
    #   • outer paginates `configs_groups[]` (group section headers)
    #   • inner expands selected groups into `configs[]` rows
    # `configs_expanded` is the set of group_ids the user has opened;
    # only those groups' rows are returned (capped per group). The
    # client owns expansion state via URL params (nuqs).
    configs_groups_page: int = Field(1, ge=1, description="1-indexed page of group section headers")
    configs_groups_page_size: int = Field(10, ge=1, le=100, description="Group headers per page")
    configs_expanded: list[UUID] = Field(
        default_factory=list,
        description="Group IDs the user has expanded; rows fetched only for these",
    )
    configs_expanded_page_size: int = Field(20, ge=1, le=200, description="Rows per expanded group")
    configs_search: str | None = Field(None, description="Free-text filter on group name")

    # Picker selection — the run_ids the user has currently picked for
    # the next Run. Server loads each selected run's historical
    # messages so the client can preview them inline (dashed-border
    # cards) interleaved with the test's actual history bindings. None
    # / empty → no preview messages loaded.
    configs_selected: list[UUID] = Field(
        default_factory=list,
        description="Run IDs currently selected in the picker; messages preloaded for preview",
    )


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


class TestConfigItem(BaseModel):
    """A reusable run configuration the picker can queue.

    Sources from runs_entry rows. Each row is a distinct config
    (agent + model + bundle) that can be re-fired any number of times
    into fresh trace executions. The bundle ids carried here come from
    the historical run's agent_resource — the picker passes them as
    `RunPanelState` to /test/trace so the new trace records the same
    prompt + tool + instruction set the original run executed against.
    """

    run_id: str = Field(..., description="UUID of the runs_entry config")
    group_id: str | None = Field(None, description="UUID of the parent group (for grouping in the picker)")
    agent_name: str | None = Field(None, description="Display name of the agent")
    model_name: str | None = Field(None, description="Display name of the underlying model")
    label: str = Field(..., description="Human-readable picker label")
    created_at: str | None = Field(None, description="When this config was first created")

    # Bundle ids from the historical run's agent_resource. The server
    # resolves them once here so the picker can pass them as panel
    # state to /test/trace for faithful replay — no agent lookup on
    # the client, no per-trace agent override on the server.
    prompt_ids: list[str] = Field(default_factory=list, description="Prompt resource ids from the historical agent")
    tool_ids: list[str] = Field(default_factory=list, description="Tool resource ids from the historical agent")
    instruction_ids: list[str] = Field(default_factory=list, description="Instruction resource ids from the historical agent")

    # Snapshot of the historical agent_resource's tunable settings.
    # Mirrors the raw fields on ``GetAgentResponse`` (not level ids) so
    # the panel can prefill exactly what the run executed against. The
    # client matches each value back to the model's available
    # ``temperature_levels`` / ``reasoning_levels`` / ``qualities``
    # chips in ``resources.*`` for selection state. ``model_id`` lets
    # the panel look up the model's chip catalog.
    model_id: str | None = Field(None, description="Model id from the historical agent")
    temperature: float | None = Field(None, description="Temperature value from the historical agent")
    reasoning: str | None = Field(None, description="Reasoning level value from the historical agent")
    quality: str | None = Field(None, description="Quality value from the historical agent")

    # Historical permissions: ``(artifact, operation)`` pairs the
    # historical run actually executed, parsed from each call's
    # persisted ``events`` log. The client filters the tools picker by
    # the union of the currently-selected runs' permissions — so the
    # user only sees tools that grant operations the replay tape can
    # serve. See project_test_replay_design memory.
    permissions: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Historical (artifact, operation) pairs this run executed",
    )


class TestConfigGroup(BaseModel):
    """A group bucket for the picker — used as the section header.

    Renders one accordion section per row. `run_count` is the total
    rows in the group (across the whole inner pagination universe,
    not just the current expanded window). `last_run_at` drives the
    outer ordering (most-recent-group first).
    """

    group_id: str = Field(..., description="UUID of the group")
    name: str | None = Field(None, description="Human-readable group name (or null if unnamed)")
    run_count: int = Field(0, description="Total run configs in this group")
    last_run_at: str | None = Field(None, description="ISO timestamp of the most recent run in this group")


class TestStatusSummary(BaseModel):
    total: int = Field(0, description="Total number of invocations")
    completed: int = Field(0, description="Number of completed invocations")
    in_progress: int = Field(0, description="Number of in-progress invocations")
    not_started: int = Field(0, description="Number of not-started invocations")


# =============================================================================
# Graded-view payload (per-invocation × per-run, mirrors attempt.ChatData)
# =============================================================================
#
# An invocation is the config under test (model × agent × prompt × tools ×
# rubric). Running it N times produces N runs, each with its own grade.
# ``InvocationDetail`` carries everything the graded view needs for one
# config; ``runs[]`` carries the per-execution detail (grading_state,
# transcript ids, etc.). The client picks an invocation (global switcher)
# and a run within (local switcher) to drive TableRubric + transcript +
# the right-side resource panel snapshot.


class InvocationRunDetail(BaseModel):
    """Per-run grade + replay detail within an invocation.

    One row per ``test_invocation_runs_entry`` binding. Carries the
    TableRubric-ready ``grading_state`` plus the message/call ids the
    client uses to slice ``entries.messages`` / ``entries.calls``.
    """

    run_id: UUID = Field(..., description="UUID of the runs_entry row this binding executed")
    binding_id: UUID = Field(..., description="UUID of the test_invocation_runs_entry binding row")
    grade_id: UUID | None = Field(None, description="UUID of the test_grade_entry, if graded")
    created_at: datetime | None = Field(None, description="When the binding was created")
    completed: bool = Field(False, description="Whether the binding has a completion record")
    grade: GradeData | None = Field(None, description="Score / passed / time_taken summary")
    grading_state: GradingStateData | None = Field(None, description="Achieved/passed/feedback maps keyed by standard_id")
    feedbacks: list[FeedbackEntry] | None = Field(None, description="Per-standard feedback rows")
    analyses: list[AnalysisEntry] | None = Field(None, description="Chat-level analysis content (currently unused for tests)")
    message_ids: list[UUID] | None = Field(None, description="Message ids belonging to this run")
    call_ids: list[UUID] | None = Field(None, description="Tool-call ids belonging to this run")


class InvocationDetail(BaseModel):
    """Per-invocation graded-view payload.

    Mirrors ``ChatData`` from attempt — one of these per invocation,
    each carrying its rubric structure and the list of runs that
    executed against it. ``primary_run_id`` is the default local
    selection (usually the most recent / row-summary grade).
    """

    invocation_id: UUID = Field(..., description="UUID of the test_invocation_entry")
    rubric_id: UUID | None = Field(None, description="UUID of the rubric used to grade this invocation")
    rubric_structure: RubricStructureData | None = Field(None, description="Rubric structure for TableRubric (standards / groups / mappings)")
    primary_run_id: UUID | None = Field(None, description="Default selected run for this invocation")
    # Historical config bundle — sourced from the invocation's agent.
    # The right-side ResourcePanel renders read-only snapshots from these
    # ids by looking up resources.* keyed by id.
    agent_id: UUID | None = Field(None, description="UUID of the agent under test")
    model_id: UUID | None = Field(None, description="UUID of the model the agent is set up with")
    voice_id: UUID | None = Field(None, description="UUID of the voice resource")
    temperature_level_id: UUID | None = Field(None, description="UUID of the temperature level")
    reasoning_level_id: UUID | None = Field(None, description="UUID of the reasoning level")
    quality_id: UUID | None = Field(None, description="UUID of the quality level")
    modality_ids: list[UUID] = Field(default_factory=list, description="Modality resource ids")
    runs: list[InvocationRunDetail] = Field(default_factory=list, description="Per-execution detail")


class TestEntries(BaseModel):
    """Entry payloads grouped by type."""

    tests: list[GetTestResponse] | None = Field(None, description="Test entry payloads")
    invocations: list[GetTestInvocationResponse] | None = Field(None, description="Invocation entry payloads")
    runs: list[GetTestInvocationRunsResponse] | None = Field(None, description="Run entry payloads")
    groups: list[GetTestInvocationTracesResponse] | None = Field(None, description="Group entry payloads")
    grades: list[GetTestGradeResponse] | None = Field(None, description="Grade entry payloads")
    feedback: list[GetTestFeedbackResponse] | None = Field(None, description="Feedback entry payloads")
    messages: list[SearchMessageResponse] | None = Field(None, description="Message entry payloads")
    calls: list | None = Field(None, description="Tool call entries from original run")


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
    standard_groups: dict[str, dict] | None = Field(None, description="Standard group resources keyed by ID")
    standards: dict[str, dict] | None = Field(None, description="Standard resources keyed by ID")


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

    # Runs derived from invocations (history zone — actual past executions)
    runs: list[TestRunItem] = Field(default_factory=list, description="Run items derived from invocations")

    # Reusable run configurations (picker zone — sourced from runs_entry
    # rows). Each can be queued to fire a fresh trace+run any number of
    # times. Two-axis pagination: `configs_groups[]` headers are the
    # outer page, `configs[]` rows are loaded only for the groups in
    # `configs_expanded` on the request.
    configs: list[TestConfigItem] = Field(default_factory=list, description="Run configs only for groups in configs_expanded")
    configs_groups: list[TestConfigGroup] = Field(default_factory=list, description="Group section headers (current outer page)")
    configs_total: int = Field(0, description="Total run configs across all groups (universe size)")
    configs_groups_total: int = Field(0, description="Total groups matching filters (outer pagination universe)")
    configs_per_group_total: dict[str, int] = Field(
        default_factory=dict,
        description="group_id → total row count (used by inner pagination 'Show more' math)",
    )

    # Status summary
    status_summary: TestStatusSummary | None = Field(None, description="Summary of invocation statuses")

    # Inline controls data (replaces auth/group resolution for toolbar)
    show_controls: bool = Field(False, description="Whether to show UI controls")
    current_invocation_id: str | None = Field(None, description="ID of the current invocation")
    has_runs_or_groups: bool = Field(False, description="Whether the test has runs or groups")

    # Client-orchestrated state machine — next pending invocation, mirrors
    # /attempt/get.next_chat_entry_id. Null when all invocations are done.
    next_invocation_id: str | None = Field(
        None, description="UUID of the next uncompleted invocation, or null if all are done"
    )

    # Graded-view payload — one ``InvocationDetail`` per invocation,
    # each with its rubric_structure + per-run grading_state. Mirrors
    # attempt.entries.attempt_chat[] for the canonical pattern.
    invocation_details: list[InvocationDetail] = Field(
        default_factory=list,
        description="Per-invocation graded payloads (rubric_structure + runs[] with grading_state)",
    )

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


class ExportTestApiRequest(BaseModel):
    """Request model for view-aware test export.

    Views: ``single`` (one test_id), ``benchmark`` (analytics), ``invocation``.
    All views return the canonical ``{file_id, file_name, row_count}`` shape;
    client downloads via ``/api/test/download/{file_id}``.
    """

    view: str = Field(
        "single",
        description="View discriminator: 'single' | 'benchmark' | 'invocation'",
    )
    test_id: UUID | None = Field(None, description="UUID of the target test (required for 'single' and 'invocation')")
    invocation_id: UUID | None = Field(None, description="UUID of the target invocation entry (optional for 'invocation')")
    draft_id: UUID | None = Field(None, description="Optional draft id for 'invocation' view")
    mode: str | None = Field(
        None,
        description="Optional sub-mode within a view. Currently recognized: "
                    "view=reports → mode='brightspace' (gradebook CSV only); "
                    "view=home → mode='certificate' (PDF cert only) or 'attempts' (CSV only). "
                    "Default (None) returns the full per-view bundle.",
    )


class ExportTestApiResponse(BaseModel):
    """Response model for test export — canonical file modality."""

    file_id: UUID = Field(..., description="UUID of the files_resource holding the export bytes")
    file_name: str = Field(..., description="Suggested download file name")
    row_count: int = Field(..., description="Number of data rows in the export")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsTestApiRequest(BaseModel):
    """Request model for test generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsTestListItem(BaseModel):
    """Single generation group in the test generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsTestApiResponse(BaseModel):
    """Response model for test generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsTestListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemTestApiRequest(BaseModel):
    """Request model for test problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")


class ProblemTestApiResponse(BaseModel):
    """Response model for test problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
