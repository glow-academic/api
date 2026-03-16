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
    run_id: UUID
    call_id: UUID
