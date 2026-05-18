"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestInvocationRunsCompletionResponse(BaseModel):
    id: UUID


class GetTestInvocationRunsCompletionResponse(BaseModel):
    id: UUID
    test_invocation_runs_id: UUID
    stop: bool
    error: bool
    message: str
    call_id: UUID | None = None
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
