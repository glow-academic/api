"""Types for options resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetOptionResponse(BaseModel):
    id: UUID
    option_text: str
    is_correct: bool
    question_id: UUID | None
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
