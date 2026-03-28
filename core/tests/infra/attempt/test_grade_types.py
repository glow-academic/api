"""Tests for attempt grade_types — Pydantic models."""
import pytest
from app.infra.attempt.grade_types import (
    GradeAttemptRequest, AttemptGradeFeedbackEntry,
    AttemptGradeStrengthEntry, AttemptGradeImprovementEntry,
)
from uuid import uuid4
pytestmark = pytest.mark.asyncio

async def test_grade_request_requires_attempt_id():
    req = GradeAttemptRequest(attempt_id=uuid4())
    assert req.attempt_id is not None

async def test_feedback_entry():
    entry = AttemptGradeFeedbackEntry(feedback="Good job", total=90)
    assert entry.feedback == "Good job"
    assert entry.total == 90

async def test_strength_entry():
    entry = AttemptGradeStrengthEntry(name="Communication", description="Clear")
    assert entry.name == "Communication"
