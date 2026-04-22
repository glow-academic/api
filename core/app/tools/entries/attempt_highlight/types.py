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
    # idx lives on attempt_highlight_entry but isn't projected to
    # attempt_highlight_mv — keep optional here so the search dict
    # unpack doesn't crash. Follow-up migration should add the
    # column to the MV and make this required again.
    idx: int | None = None
    created_at: datetime
