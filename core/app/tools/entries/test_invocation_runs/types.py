"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestInvocationRunsResponse(BaseModel):
    id: UUID


class GetTestInvocationRunsResponse(BaseModel):
    id: UUID
    test_invocation_id: UUID
    test_invocation_traces_id: UUID | None = None
    run_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    generated: bool
    mcp: bool
    active: bool
