"""Practice chat entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreatePracticeChatResponse(BaseModel):
    id: UUID


class GetPracticeChatResponse(BaseModel):
    id: UUID
    practice_id: UUID
    chat_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    session_id: UUID
