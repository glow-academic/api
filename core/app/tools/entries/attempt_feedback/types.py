"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptFeedbackResponse(BaseModel):
    id: UUID


class GetAttemptFeedbackResponse(BaseModel):
    feedback_id: UUID
    grade_id: UUID
    total: int
    score: int
    feedback: str
    created_at: datetime
