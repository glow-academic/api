"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptHintResponse(BaseModel):
    id: UUID


class GetAttemptHintResponse(BaseModel):
    hint_id: UUID
    message_id: UUID
    hint: str
    idx: int
    created_at: datetime
