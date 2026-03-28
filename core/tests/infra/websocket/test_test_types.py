"""Tests for test_types — Pydantic models for test-domain bus emits."""

from __future__ import annotations

import pytest

from app.infra.websocket.test_types import (
    TestAllCompleteEvent,
    TestErrorData,
    TestGradedData,
    TestProceedData,
    TestProgressData,
    TestRunCompleteData,
)

pytestmark = pytest.mark.asyncio


async def test_test_progress_data_defaults():
    """TestProgressData has correct defaults for optional fields."""
    data = TestProgressData(invocation_id="inv-123")

    assert data.invocation_id == "inv-123"
    assert data.sid is None
    assert data.rooms == []
    assert data.run_id is None
    assert data.current_run is None
    assert data.total_runs is None
    assert data.message is None


async def test_test_run_complete_data_with_all_fields():
    """TestRunCompleteData accepts all fields correctly."""
    data = TestRunCompleteData(
        invocation_id="inv-456",
        sid="socket-1",
        rooms=["room-a", "room-b"],
        run_id="run-789",
        original_run_resource_id="orig-run",
        tool_calls=[{"name": "search"}],
        current_run=2,
        total_runs=5,
        remaining_runs=3,
    )

    assert data.invocation_id == "inv-456"
    assert data.current_run == 2
    assert data.total_runs == 5
    assert data.remaining_runs == 3
    assert len(data.rooms) == 2


async def test_test_graded_data_fields():
    """TestGradedData carries grade results."""
    data = TestGradedData(
        invocation_id="inv-1",
        grade_id="grade-1",
        score=85,
        passed=True,
        feedback="Good job",
    )

    assert data.score == 85
    assert data.passed is True
    assert data.feedback == "Good job"


async def test_test_proceed_data_requires_sid_and_test_id():
    """TestProceedData requires sid and test_id."""
    data = TestProceedData(sid="s1", test_id="t1")

    assert data.sid == "s1"
    assert data.test_id == "t1"
    assert data.force_proceed is False
    assert data.complete_all is False


async def test_test_error_data_carries_message():
    """TestErrorData carries error message and type."""
    data = TestErrorData(message="Something failed", error_type="timeout")

    assert data.message == "Something failed"
    assert data.error_type == "timeout"
    assert data.invocation_id is None


async def test_test_all_complete_event():
    """TestAllCompleteEvent defaults success to True."""
    event = TestAllCompleteEvent(invocation_id="inv-1", total_runs=10)

    assert event.success is True
    assert event.total_runs == 10
    assert event.invocation_id == "inv-1"


async def test_model_serialization_roundtrip():
    """Pydantic models serialize and deserialize correctly."""
    original = TestRunCompleteData(
        invocation_id="inv-1",
        current_run=3,
        total_runs=5,
    )
    data = original.model_dump()
    restored = TestRunCompleteData(**data)

    assert restored.invocation_id == original.invocation_id
    assert restored.current_run == original.current_run
