"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestFeedbackResponse(BaseModel):
    id: UUID


class GetTestFeedbackResponse(BaseModel):
    feedback_id: UUID
    grade_id: UUID
    call_id: UUID
    tool_call_id: UUID
    # Per-standard attribution via the shared ``feedbacks_standards_connection``
    # table. Nullable for legacy rows written before the connection was
    # populated (and for the LEFT JOIN miss case).
    standard_id: UUID | None = None
    total: int
    feedback: str
    total_points: int
    pass_points: int
    created_at: datetime
