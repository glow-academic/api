"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestCompletionResponse(BaseModel):
    id: UUID


class GetTestCompletionResponse(BaseModel):
    id: UUID
    test_id: UUID
    stop: bool
    error: bool
    message: str
    call_id: UUID | None = None
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
