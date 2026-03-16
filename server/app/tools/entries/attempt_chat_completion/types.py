"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptChatCompletionResponse(BaseModel):
    id: UUID


class GetAttemptChatCompletionResponse(BaseModel):
    id: UUID
    chat_id: UUID
    stop: bool
    error: bool
    message: str
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    call_id: UUID
