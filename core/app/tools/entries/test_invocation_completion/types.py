"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestInvocationCompletionResponse(BaseModel):
    id: UUID


class GetTestInvocationCompletionResponse(BaseModel):
    id: UUID
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
    invocation_id: UUID
    stop: bool
    error: bool
    message: str
    call_id: UUID
