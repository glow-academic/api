"""Home chat entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateHomeChatResponse(BaseModel):
    id: UUID


class GetHomeChatResponse(BaseModel):
    id: UUID
    home_id: UUID
    chat_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    session_id: UUID
