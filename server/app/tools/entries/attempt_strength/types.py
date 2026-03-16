"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptStrengthResponse(BaseModel):
    id: UUID


class GetAttemptStrengthResponse(BaseModel):
    strength_id: UUID
    message_id: UUID
    grade_id: UUID
    name: str
    description: str
    created_at: datetime
