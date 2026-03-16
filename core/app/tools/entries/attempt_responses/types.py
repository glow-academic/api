"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptResponsesResponse(BaseModel):
    id: UUID


class GetAttemptResponsesResponse(BaseModel):
    response_id: UUID
    chat_id: UUID
    question_id: UUID | None
    option_id: UUID | None
    created_at: datetime
