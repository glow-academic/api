"""Sessions entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateSessionResponse(BaseModel):
    id: UUID


class GetSessionResponse(BaseModel):
    id: UUID
    profile_id: UUID
    created_at: datetime
    active: bool
    mcp: bool
