"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptConversationCompletionResponse(BaseModel):
    id: UUID


class GetAttemptConversationCompletionResponse(BaseModel):
    id: UUID
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
    conversation_id: UUID
    stop: bool
    error: bool
    message: str
    call_id: UUID
