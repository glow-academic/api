"""Files entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateFileResponse(BaseModel):
    id: UUID


class GetFileResponse(BaseModel):
    id: UUID
    session_id: UUID
    active: bool
    mcp: bool
    generated: bool


class SearchFileResponse(BaseModel):
    file_id: UUID
    files_id: UUID | None = None
    upload_id: UUID | None = None
    file_path: str | None = None
    mime_type: str | None = None
    size: int | None = None
    created_at: datetime
