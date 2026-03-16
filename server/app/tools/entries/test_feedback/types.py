"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestFeedbackResponse(BaseModel):
    id: UUID


class GetTestFeedbackResponse(BaseModel):
    feedback_id: UUID
    grade_id: UUID
    total: int
    feedback: str
    total_points: int
    pass_points: int
    created_at: datetime
