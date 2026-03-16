"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptHighlightResponse(BaseModel):
    id: UUID


class GetAttemptHighlightResponse(BaseModel):
    highlight_id: UUID
    strength_id: UUID
    section: str
    idx: int
    created_at: datetime
