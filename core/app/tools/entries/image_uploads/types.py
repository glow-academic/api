"""Image uploads entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateImageUploadResponse(BaseModel):
    id: UUID


class GetImageUploadResponse(BaseModel):
    id: UUID
    image_id: UUID
    upload_id: UUID
    session_id: UUID
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
