"""Types for attempt_audio entry."""

from uuid import UUID

from pydantic import BaseModel


class CreateAttemptAudioResponse(BaseModel):
    id: UUID
