"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateTestArchiveResponse(BaseModel):
    id: UUID


class GetTestArchiveResponse(BaseModel):
    id: UUID
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
    test_id: UUID
    archived: bool
    call_id: UUID
