"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptImprovementResponse(BaseModel):
    id: UUID


class GetAttemptImprovementResponse(BaseModel):
    improvement_id: UUID
    message_id: UUID
    name: str
    description: str
    created_at: datetime
