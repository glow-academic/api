"""Test invocation entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestInvocationResponse(BaseModel):
    id: UUID


class GetTestInvocationResponse(BaseModel):
    invocation_id: UUID
    test_id: UUID | None
    group_id: UUID | None
    invocation_created_at: datetime
    invocation_title: str
    use_custom: bool
    position: int
    invocation_completed: bool
    grade_id: UUID | None
    grade_score: float | None
    grade_passed: bool | None
    grade_time_taken: float | None
    rubric_id: UUID | None
    agent_ids: list[UUID] = []
    quality_id: UUID | None = None
    department_ids: list[UUID] = []
    run_agent_ids: list[UUID] = []
    group_agent_ids: list[UUID] = []
    voice_id: UUID | None = None
    temperature_level_id: UUID | None = None
    reasoning_level_id: UUID | None = None
    modality_ids: list[UUID] = []
