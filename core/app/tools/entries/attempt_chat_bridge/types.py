"""Attempt chat bridge entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptChatBridgeResponse(BaseModel):
    attempt_id: UUID
    attempt_chat_id: UUID


class GetAttemptChatBridgeResponse(BaseModel):
    attempt_id: UUID
    attempt_chat_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    session_id: UUID
