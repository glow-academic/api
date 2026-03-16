"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptGradeResponse(BaseModel):
    id: UUID


class GetAttemptGradeResponse(BaseModel):
    grade_id: UUID
    chat_id: UUID
    score: float
    passed: bool
    time_taken: int | None
    total_points: int | None
    pass_points: int | None
    rubric_id: UUID | None
    created_at: datetime
