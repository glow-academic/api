"""Images entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateImageResponse(BaseModel):
    id: UUID


class GetImageResponse(BaseModel):
    id: UUID
    session_id: UUID
    active: bool
    mcp: bool
    generated: bool


class SearchImageResponse(BaseModel):
    image_id: UUID
    images_id: UUID | None = None
    upload_id: UUID | None = None
    file_path: str | None = None
    mime_type: str | None = None
    size: int | None = None
    quality_id: UUID | None = None
    created_at: datetime
