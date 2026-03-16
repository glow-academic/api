"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptMutesResponse(BaseModel):
    id: UUID


class GetAttemptMutesResponse(BaseModel):
    id: UUID
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
    conversation_id: UUID
    muted: bool
    call_id: UUID
