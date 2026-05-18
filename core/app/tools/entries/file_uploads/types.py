"""File uploads entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateFileUploadResponse(BaseModel):
    id: UUID


class GetFileUploadResponse(BaseModel):
    id: UUID
    file_id: UUID
    upload_id: UUID
    session_id: UUID
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
