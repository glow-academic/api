"""Texts entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTextResponse(BaseModel):
    id: UUID


class GetTextResponse(BaseModel):
    id: UUID
    session_id: UUID
    active: bool
    mcp: bool
    generated: bool


class SearchTextResponse(BaseModel):
    texts_id: UUID
    text_id: UUID
    upload_id: UUID | None
    file_path: str | None
    mime_type: str | None
    created_at: datetime
