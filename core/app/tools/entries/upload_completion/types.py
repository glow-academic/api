"""Uploads completions entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateUploadCompletionResponse(BaseModel):
    id: UUID


class GetUploadCompletionResponse(BaseModel):
    id: UUID
    upload_id: UUID
    session_id: UUID
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
    stop: bool
    error: bool
    message: str


class SearchUploadCompletionResponse(BaseModel):
    id: UUID
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
    upload_id: UUID
    session_id: UUID
    stop: bool
    error: bool
    message: str
