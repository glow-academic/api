"""Types for questions resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetQuestionResponse(BaseModel):
    id: UUID
    question_text: str
    allow_multiple: bool
    time: int
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
