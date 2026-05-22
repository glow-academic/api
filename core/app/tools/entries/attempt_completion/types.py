"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptCompletionResponse(BaseModel):
    id: UUID


class GetAttemptCompletionResponse(BaseModel):
    id: UUID
    attempt_id: UUID
    stop: bool
    error: bool
    message: str
    session_id: UUID | None = None
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
