"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptConversationsResponse(BaseModel):
    id: UUID


class GetAttemptConversationsResponse(BaseModel):
    id: UUID
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
    chat_id: UUID
    session_id: UUID | None = None
