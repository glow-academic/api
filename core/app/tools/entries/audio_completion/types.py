"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAudioCompletionResponse(BaseModel):
    id: UUID
    # True iff the row is an MV-visible (hard) completion (C1-B).
    active: bool = True


class GetAudioCompletionResponse(BaseModel):
    id: UUID
    audio_id: UUID
    stop: bool
    error: bool
    message: str
    session_id: UUID | None = None
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
