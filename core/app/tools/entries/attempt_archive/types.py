"""Entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptArchiveResponse(BaseModel):
    id: UUID


class GetAttemptArchiveResponse(BaseModel):
    id: UUID
    created_at: datetime
    generated: bool
    mcp: bool
    active: bool
    attempt_id: UUID
    archived: bool
    call_id: UUID
