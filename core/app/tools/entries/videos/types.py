"""Videos entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateVideoResponse(BaseModel):
    id: UUID


class GetVideoResponse(BaseModel):
    id: UUID
    session_id: UUID
    length_seconds: int
    active: bool
    mcp: bool
    generated: bool


class SearchVideoResponse(BaseModel):
    video_id: UUID
    videos_id: UUID | None = None
    upload_id: UUID | None = None
    file_path: str | None = None
    mime_type: str | None = None
    size: int | None = None
    length_seconds: int
    created_at: datetime
