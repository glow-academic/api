"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestGradeResponse(BaseModel):
    id: UUID


class GetTestGradeResponse(BaseModel):
    id: UUID
    invocation_id: UUID
    run_id: UUID | None
    created_at: datetime
    updated_at: datetime
    passed: bool
    score: int
    time_taken: int | None
    generated: bool
    mcp: bool
    active: bool
    call_id: UUID | None
