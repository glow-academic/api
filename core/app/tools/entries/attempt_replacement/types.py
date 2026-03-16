"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptReplacementResponse(BaseModel):
    id: UUID


class GetAttemptReplacementResponse(BaseModel):
    replacement_id: UUID
    improvement_id: UUID
    section: str
    replace_text: str
    idx: int
    created_at: datetime
