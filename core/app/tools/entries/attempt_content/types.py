"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptContentResponse(BaseModel):
    id: UUID


class GetAttemptContentResponse(BaseModel):
    content_id: UUID
    message_id: UUID
    content: str
    persona_entry_id: UUID | None
    idx: int
    created_at: datetime
