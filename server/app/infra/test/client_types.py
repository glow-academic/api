"""Client-facing WebSocket types for the Test domain.

Canonical location for all Test* payload and event types used between
the client and server over WebSocket / SSE.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_GRADE_ENTRY_TYPES = ["grades", "feedbacks"]

# ---------------------------------------------------------------------------
# Test room management
# ---------------------------------------------------------------------------


class TestJoinPayload(BaseModel):
    """Client-to-server: join a test room for real-time updates."""

    invocation_id: UUID = Field(..., description="UUID of the test invocation to join")


class TestLeavePayload(BaseModel):
    """Client-to-server: leave a test room."""

    invocation_id: UUID = Field(..., description="UUID of the test invocation to leave")


class TestStartPayload(BaseModel):
    """Client-to-server: create a new test."""

    benchmark_id: UUID = Field(..., description="UUID of the benchmark to test against")
    infinite_mode: bool = Field(False, description="Whether to run in infinite mode")


class TestNextPayload(BaseModel):
    """Client-to-server: find next pending run in an existing test."""

    test_id: UUID = Field(..., description="UUID of the test")


class TestRunPayload(BaseModel):
    """Client-to-server: run one replay against an original run."""

    test_id: UUID = Field(..., description="UUID of the test")
    test_invocation_id: UUID = Field(..., description="UUID of the test invocation")
    run_id: UUID = Field(..., description="Original run to replay")


class TestGroupPayload(BaseModel):
    """Client-to-server: run all runs in a group sequentially."""

    test_id: UUID = Field(..., description="UUID of the test")
    test_invocation_id: UUID = Field(..., description="UUID of the test invocation")
    prev_run_id: UUID | None = Field(None, description="Previous run ID; None starts from first run")


class TestEndPayload(BaseModel):
    """Client-to-server: end a single invocation within a test."""

    test_id: UUID = Field(..., description="UUID of the test")
    test_invocation_id: UUID = Field(..., description="UUID of the test invocation")
    run_id: UUID = Field(..., description="UUID of the completed run for grading")
    grade: bool = Field(True, description="Whether to grade this run")


class TestEndAllPayload(BaseModel):
    """Client-to-server: end all remaining invocations in a test."""

    test_id: UUID = Field(..., description="UUID of the test")


class TestStopPayload(BaseModel):
    """Client-to-server: stop current test execution."""

    invocation_id: UUID = Field(..., description="UUID of the test invocation to stop")


class TestJoinedEvent(BaseModel):
    """Server-to-client: successfully joined a test room."""

    invocation_id: str = Field(..., description="UUID of the test invocation")
    success: bool = Field(True, description="Whether the join succeeded")


class TestStartedEvent(BaseModel):
    """Server-to-client: test created."""

    test_id: str = Field(..., description="UUID of the created test")


class TestRunStartEvent(BaseModel):
    """Server-to-client: run replay started."""

    invocation_id: str = Field(..., description="UUID of the test invocation")
    run_id: str = Field(..., description="UUID of the test run")
    original_run_resource_id: str | None = Field(None, description="Resource ID of the original run")
    current_run: int = Field(..., description="Current run index (1-based)")
    total_runs: int = Field(..., description="Total number of runs in this invocation")
    created_at: str = Field(..., description="ISO 8601 timestamp of run creation")


class TestRunDeltaEvent(BaseModel):
    """Server-to-client: generation progress delta."""

    invocation_id: str = Field(..., description="UUID of the test invocation")
    run_id: str = Field(..., description="UUID of the test run")
    content: str = Field(..., description="Incremental text update")


class TestRunCompleteEvent(BaseModel):
    """Server-to-client: single run replay completed."""

    invocation_id: str = Field(..., description="UUID of the test invocation")
    run_id: str = Field(..., description="UUID of the test run")
    original_run_resource_id: str | None = Field(None, description="Resource ID of the original run")
    tool_calls: list[dict[str, Any]] | None = Field(None, description="Tool calls made during the run")
    current_run: int = Field(..., description="Current run index (1-based)")
    total_runs: int = Field(..., description="Total number of runs in this invocation")
    remaining_runs: int = Field(..., description="Number of runs still pending")


class TestAllCompleteEvent(BaseModel):
    """Server-to-client: all runs complete."""

    invocation_id: str = Field(..., description="UUID of the test invocation")
    total_runs: int = Field(..., description="Total number of completed runs")
    success: bool = Field(True, description="Whether all runs succeeded")


class TestGradedEvent(BaseModel):
    """Server-to-client: grading completed."""

    invocation_id: str = Field(..., description="UUID of the test invocation")
    grade_id: str | None = Field(None, description="UUID of the grade record")
    score: float | None = Field(None, description="Numeric grade score")
    passed: bool | None = Field(None, description="Whether the test passed")
    feedback: str | None = Field(None, description="Grading feedback text")


class TestProgressEvent(BaseModel):
    """Server-to-client: test progress update."""

    invocation_id: str = Field(..., description="UUID of the test invocation")
    type: str = Field(..., description="Progress event type")
    run_id: str | None = Field(None, description="UUID of the test run")
    current_run: int | None = Field(None, description="Current run index (1-based)")
    total_runs: int | None = Field(None, description="Total number of runs")
    message: str | None = Field(None, description="Event message content")


class TestStoppedEvent(BaseModel):
    """Server-to-client: test execution stopped."""

    invocation_id: str = Field(..., description="UUID of the test invocation")
    success: bool = Field(True, description="Whether the stop succeeded")
    message: str | None = Field(None, description="Event message content")


class TestErrorEvent(BaseModel):
    """Server-to-client: test error."""

    invocation_id: str | None = Field(None, description="UUID of the test invocation")
    run_id: str | None = Field(None, description="UUID of the test run")
    message: str = Field(..., description="Error message")
    error_type: str | None = Field(None, description="Classification of the error")
