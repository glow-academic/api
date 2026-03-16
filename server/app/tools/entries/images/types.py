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
    images_id: UUID
    upload_id: UUID
    file_path: str
    mime_type: str
    size: int
    quality_id: UUID | None
    created_at: datetime
