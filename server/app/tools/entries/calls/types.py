"""Calls entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateCallResponse(BaseModel):
    id: UUID


class GetCallResponse(BaseModel):
    id: UUID
    run_id: UUID
    session_id: UUID
    external_call_id: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool


class SearchCallResponse(BaseModel):
    call_id: UUID
    run_id: UUID
    call_created_at: datetime
    upload_id: UUID | None
    file_path: str | None
    mime_type: str | None
    tool_id: UUID | None
