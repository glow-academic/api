"""Uploads entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateUploadResponse(BaseModel):
    id: UUID


class GetUploadResponse(BaseModel):
    id: UUID
    session_id: UUID
    file_path: str
    mime_type: str
    size: int
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool


class SearchUploadResponse(BaseModel):
    upload_id: UUID
    file_path: str
    mime_type: str
    size: int
    created_at: datetime
