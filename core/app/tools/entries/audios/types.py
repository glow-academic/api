"""Audios entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAudioResponse(BaseModel):
    id: UUID


class GetAudioResponse(BaseModel):
    id: UUID
    session_id: UUID
    length_seconds: int
    active: bool
    mcp: bool
    generated: bool


class SearchAudioResponse(BaseModel):
    audio_id: UUID
    upload_id: UUID
    file_path: str
    mime_type: str
    size: int
    length_seconds: int
    voice_id: UUID | None
    created_at: datetime
