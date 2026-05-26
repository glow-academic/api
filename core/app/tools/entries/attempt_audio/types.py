"""Types for attempt_audio entry."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptAudioResponse(BaseModel):
    id: UUID


class GetAttemptAudioResponse(BaseModel):
    id: UUID
    message_id: UUID
    audios_id: UUID
    session_id: UUID | None = None
    active: bool
    mcp: bool
    generated: bool
    created_at: datetime
